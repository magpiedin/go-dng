package dng

import(
	"image"
	"image/color"
	"unsafe"
)

// #include <dng-wrapper.h>
import "C"

// Image represents one of the different images that we can pull out
// of a Negative. It is a thin wrapper over the NEagtive, and
// implements the `image.Image` interface.
type Image struct {
	k       ImageKind
	n       Negative

	cpix_  *C.CPixelBuffer // C pointer to a (CPixelBuffer *) object
}

type ImageKind int
const(
	// Ensure these constants correspond to those in the C code
	// Stage 1: raw sensor readings. We don't try and turn them into an image.
	// Stage 2: linearized raw sensor readings, in four planes (GRGB or something). Ignore this too.
	ImageStage3      ImageKind = C.ImageStage3      // dng_validate stage 3: demosaiced RGB data
	ImageFinalRender ImageKind = C.ImageFinalRender // DNG developed to final (color curve adjustments, etc)
)

func (n Negative)NewImage(k ImageKind) image.Image {
	k_ := C.int(k)
	return Image{k, n, C.GO_MakePixelBuffer(n.cneg_, k_) }
}

// Implement image.Image
func (img Image)ColorModel() color.Model { return color.RGBA64Model }
func (img Image)Bounds() image.Rectangle { return GoRect( C.GO_PixelBuffer_Bounds(img.cpix_) ) }

// Implement image.Image
func (img Image)At(x, y int) color.Color {
	abcd  := make([]uint16, 4) // space for up to four planes, in case we thoughtlessly process stage1/2 data someday

	abcd_ := (*C.uint16_t)(unsafe.Pointer(&abcd[0])) // convert a Go slice into a (uint16_t *) C array
	x_    := C.int(x)
	y_    := C.int(y)

	C.GO_PixelBuffer_GetPixel(img.cpix_, x_, y_, abcd_)

	// Blithely assume first three planes are RGB values in the range [0, 0xFFFF].
	return color.RGBA64{abcd[0], abcd[1], abcd[2], 0xFFFF}
}
