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

		img3 := n.NewImage(dng.ImageStage3)
		fmt.Printf("stage3 img: %v\n", img3.Bounds())
		WritePNG(img3, fmt.Sprintf("%s-s3.png", arg))
		
		imgFinal := n.NewImage(dng.ImageFinalRender)
		fmt.Printf("final img : %v\n", imgFinal.Bounds())
		WritePNG(imgFinal, fmt.Sprintf("%s-sF.png", arg))
	
		n.Free()
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
