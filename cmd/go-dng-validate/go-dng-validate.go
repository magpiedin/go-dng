package main

import(
	"flag"
	"fmt"
	"image"
	"image/png"
	"os"

	"github.com/abworrall/go-dng/pkg/dng"
)

func init() {
	flag.Parse()
}

func main() {
	for _, arg := range flag.Args() {
		fmt.Printf("Loading %q as a DNG file\n", arg)

		img := dng.Image{}
		img.Load(arg)

		fmt.Printf("- OriginalRawFileName: %q\n", img.OriginalRawFileName())
		fmt.Printf("- CameraWhite: %v\n", img.CameraWhite())
		fmt.Printf("- CameraToPCS: %v\n", img.CameraToPCS())
		fmt.Printf("- Negative Bounds: %v\n", img.Bounds())

		fmt.Printf("- EXIF - ExposureTime: %v\n", img.ExifExposureTime())
		fmt.Printf("- EXIF - FNumber     : %v\n", img.ExifFNumber())
		fmt.Printf("- EXIF - ISO         : %v\n", img.ExifISO())

		fname := fmt.Sprintf("%s-sF.png", arg)
		fmt.Printf("final rendered img : %s\n", fname)
		if err := WritePNG(img, fname); err != nil {
			fmt.Printf("Error saving image %s: %v\n", fname, err)
		}

		// Now dump stage3 data !
		img2 := dng.Image{ImageKind: dng.ImageStage3}
		img2.Load(arg)

		fname = fmt.Sprintf("%s-s3.png", arg)
		fmt.Printf("stage3 rendered img : %s\n", fname)
		if err := WritePNG(img2, fname); err != nil {
			fmt.Printf("Error saving s3 image %s: %v\n", fname, err)
		}
	
		img.Free()
		img2.Free()
	}
}

func WritePNG(img image.Image, filename string) error {
	if writer, err := os.Create(filename); err != nil {
		return fmt.Errorf("open+w '%s': %v", filename, err)
	} else {
		defer writer.Close()
		return png.Encode(writer, img)
	}
}
