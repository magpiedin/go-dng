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


// Negative holds all the parsed data from the DNG SDK, and exposes
// bits of it as regular Go objects.
type Negative struct {
	WhiteBalanceTemp int
	Verbose          bool
	ImageKind        ImageKind

	cneg_           *C.CNegative    // C pointer to a (CNegative *) object
}

// Vec3, Mat3, and URat are simple types to hold values returned from the DNG API
type Vec3 [3]float64
type Mat3 [9]float64 // row-at-a-time, so index == (x + y*3)
type URat [2]uint32

// New loads up the DNG file, and performs the DNG development process
func (n *Negative)Load(filename string) error {
	filename_ := C.CString(filename) // CString leaks, I think
	args_     := C.CNegativeArgs{
		white_balance_temp: C.int(n.WhiteBalanceTemp),
		image_kind: C.int(n.ImageKind),
	}
	if n.Verbose {
		args_.verbose = 1
	}
	
	n.cneg_    = C.GO_Make(filename_, args_)

	if n.cneg_ == nil {
		return fmt.Errorf("C.GO_Make() failed on DNG file")
	}
	return nil
}

// Free releases all memory associated with the negative ... hopefully
func (n *Negative)Free() {
	C.GO_Free(n.cneg_)
	n.cneg_ = nil
}

func (n Negative)OriginalRawFileName() string { return C.GoString( C.GO_OriginalRawFileName(n.cneg_) ) }

// CameraWhite returns an RGB color that should be white/neutral,
// given the white reference / color temperature used by DNG. (That
// info either comes from the camera via image metadata, or by an
// override arg set in `Neagtive`). This is basically the DNG
// AsShotNeutral.
func (n Negative)CameraWhite() Vec3           { return goVec3( C.GO_CameraWhite(n.cneg_) ) }

// CameraToPCS returns the transform matrix from camera-native RGB
// into CIEXYZ(D50?). This isn't quite the DNG ForwardMatrix, because
// it also bundles the white reference adjustment (matrix `D` in the
// DNG spec)
func (n Negative)CameraToPCS() Mat3           { return goMat3( C.GO_CameraToPCS(n.cneg_) ) }

func (n Negative)ExifExposureTime() URat { return goURat( C.GO_ExifExposureTime(n.cneg_) ) }
func (n Negative)ExifFNumber() URat      { return goURat( C.GO_ExifFNumber(n.cneg_) ) }
func (n Negative)ExifISO() int           { return int( C.GO_ExifISO(n.cneg_) ) }


// Implement image.Image
func (n Negative)Bounds() image.Rectangle { return goRect( C.GO_Bounds(n.cneg_) ) }
func (n Negative)ColorModel() color.Model { return color.RGBA64Model }
func (n Negative)At(x, y int) color.Color {
	abcd  := make([]uint16, 4) // space for up to four planes, in case we thoughtlessly process stage1/2 data someday
	abcd_ := (*C.uint16_t)(unsafe.Pointer(&abcd[0])) // convert a Go slice into a (uint16_t *) C array
	x_    := C.int(x)
	y_    := C.int(y)

	C.GO_GetPixelRGB(n.cneg_, x_, y_, abcd_)

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
