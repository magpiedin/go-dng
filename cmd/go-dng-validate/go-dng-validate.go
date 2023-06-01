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

		n := dng.Negative{}
		n.Load(arg)

		fmt.Printf("- OriginalRawFileName: %q\n", n.OriginalRawFileName())
		fmt.Printf("- CameraWhite: %v\n", n.CameraWhite())
		fmt.Printf("- CameraToPCS: %v\n", n.CameraToPCS())
		fmt.Printf("- Negative Bounds: %v\n", n.Bounds())

		fmt.Printf("- EXIF - ExposureTime: %v\n", n.ExifExposureTime())
		fmt.Printf("- EXIF - FNumber     : %v\n", n.ExifFNumber())
		fmt.Printf("- EXIF - ISO         : %v\n", n.ExifISO())

		fname := fmt.Sprintf("%s-sF.png", arg)
		fmt.Printf("final rendered img : %v (%s)\n", n.Bounds(), fname)
		if err := WritePNG(n, fname); err != nil {
			fmt.Printf("Error saving image %s: %v\n", fname, err)
		}

		// Now dump stage3 data !
		n2 := dng.Negative{ImageKind: dng.ImageStage3}
		n2.Load(arg)

		fname = fmt.Sprintf("%s-s3.png", arg)
		fmt.Printf("stage3 rendered img : %v (%s)\n", n2.Bounds(), fname)
		if err := WritePNG(n2, fname); err != nil {
			fmt.Printf("Error saving s3 image %s: %v\n", fname, err)
		}
	
		n.Free()
		n2.Free()
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
