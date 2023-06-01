package dng

// Note: CGO builds with PWD being the dir this file is in, e.g.
// ~/go/src/github.com/abworrall/go-dng/pkg/dng, so the repo root is
// `../..`
// Set flags to access build/*h, sdk/include/*h, and sdk/lib/*a

// #cgo CXXFLAGS: -I../../sdk/include -I../../build -ggdb3 -O0
// #cgo LDFLAGS: -L../../sdk/lib -ldng -lxmp -lz -lexpat
// #include <dng-wrapper.h>
import "C"

import(
	"fmt"
	"image"
	"image/color"
	"unsafe"
)

// Convention: trailing underscores in field/variable names mean it
// holds a C type.

type ImageKind int
const(
	// Stage 1: raw sensor readings. We don't try and turn them into an image.
	// Stage 2: linearized raw sensor readings, in four planes (GRGB or something). Ignore this too.
	ImageStage3      ImageKind = C.ImageStage3      // dng_validate stage 3: demosaiced RGB data
	ImageFinalRender ImageKind = C.ImageFinalRender // DNG developed to final (color curve adjustments, etc)
)


// An Image holds all the parsed data from the DNG SDK, exposes
// bits of it as regular Go objects, and implements `image.Image`.
type Image struct {
	WhiteBalanceTemp int       // To override the white balance recorded by the camera
	Verbose          bool      // The DNG libraries full dump of metadata
	ImageKind        ImageKind // Set this to see Stage3 data

	cneg_           *C.CNegative    // C pointer to a (CNegative *) object
}

// Vec3, Mat3, and URat are simple types to hold values returned from the DNG API
type Vec3 [3]float64
type Mat3 [9]float64 // row-at-a-time, so index == (x + y*3)
type URat [2]uint32

// New loads up the DNG file, and performs the DNG development process
func (img *Image)Load(filename string) error {
	filename_ := C.CString(filename) // CString leaks, I think
	args_     := C.CNegativeArgs{
		white_balance_temp: C.int(img.WhiteBalanceTemp),
		image_kind: C.int(img.ImageKind),
	}
	if img.Verbose {
		args_.verbose = 1
	}
	
	img.cneg_    = C.GO_Make(filename_, args_)

	if img.cneg_ == nil {
		return fmt.Errorf("C.GO_Make() failed on DNG file")
	}
	return nil
}

// Free releases all memory associated with the negative ... hopefully
func (img *Image)Free() {
	C.GO_Free(img.cneg_)
	img.cneg_ = nil
}

func (img Image)OriginalRawFileName() string { return C.GoString( C.GO_OriginalRawFileName(img.cneg_) ) }

// CameraWhite returns an RGB color that should be white/neutral,
// given the white reference / color temperature used by DNG. (That
// info either comes from the camera via image metadata, or by an
// override arg set in `Neagtive`). This is basically the DNG
// AsShotNeutral.
func (img Image)CameraWhite() Vec3           { return goVec3( C.GO_CameraWhite(img.cneg_) ) }

// CameraToPCS returns the transform matrix from camera-native RGB
// into CIEXYZ(D50?). This isn't quite the DNG ForwardMatrix, because
// it also bundles the white reference adjustment (matrix `D` in the
// DNG spec)
func (img Image)CameraToPCS() Mat3           { return goMat3( C.GO_CameraToPCS(img.cneg_) ) }

func (img Image)ExifExposureTime() URat { return goURat( C.GO_ExifExposureTime(img.cneg_) ) }
func (img Image)ExifFNumber() URat      { return goURat( C.GO_ExifFNumber(img.cneg_) ) }
func (img Image)ExifISO() int           { return int( C.GO_ExifISO(img.cneg_) ) }


// Implement image.Image
func (img Image)Bounds() image.Rectangle { return goRect( C.GO_Bounds(img.cneg_) ) }
func (img Image)ColorModel() color.Model { return color.RGBA64Model }
func (img Image)At(x, y int) color.Color {
	abcd  := make([]uint16, 4) // space for up to four planes, in case we thoughtlessly process stage1/2 data someday
	abcd_ := (*C.uint16_t)(unsafe.Pointer(&abcd[0])) // convert a Go slice into a (uint16_t *) C array
	x_    := C.int(x)
	y_    := C.int(y)

	C.GO_GetPixelRGB(img.cneg_, x_, y_, abcd_)

	// Blithely assume first three planes are RGB values in the range [0, 0xFFFF].
	return color.RGBA64{abcd[0], abcd[1], abcd[2], 0xFFFF}
}

// GoVec3 converts a C return type (CVec3, a type we define in the C wrapper file)
// to a Go Vec3.
func goVec3(in_ C.CVec3) (out Vec3) {
	for i:=0; i<3; i++ {
		out[i] = float64(in_.v[i])
	}
	return out
}

func goMat3(in_ C.CMat3) (out Mat3) {
	for i:=0; i<9; i++ {
		out[i] = float64(in_.v[i])
	}
	return out
}

func goRect(in_ C.CRect) (image.Rectangle) {
	v := [4]int{}
	for i:=0; i<4; i++ {
		v[i] = int(in_.v[i])
	}
	return image.Rectangle{image.Point{v[0], v[1]}, image.Point{v[2], v[3]}}
}

func goURat(in_ C.CURat) (out URat) {
	out[0] = uint32(in_.v[0])
	out[1] = uint32(in_.v[1])
	return out
}
