# The DNG SDK for linux & go

Adobe's DNG SDK comes with only partial support for Linux. The
makefiles in this repo will fetch and compile version 1.6 of the SDK
on Linux (tested on Ubuntu 23.04), building the SDK as two static
libraries that end up in `./sdk/lib`.

It also compiles the `dng_validate` command that comes with the SDK.

## Building the SDK on Linux

```
sudo apt install build-essentials zlib1g-dev libexpat1-dev

git clone https://github.com/abworrall/go-dng.git
cd go-dng

cd ./sdk
make

./bin/dng_validate -v your.dng
```

Indebted to https://github.com/yanburman/dng_sdk, who did all the work
for v1.4

Caveats:
- the makefiles aren't smart
- completely ignores all the CMake stuff in the bundled XML library

## Using the SDK from Go

There is also a Go wrapper around the lib, that will load and
DNG-develop a DNG file, and present it as a standard golang
`image.Image`.

I don't know of a way to make `go get` work with this lib, as building
it requires running a makefile. So you'll need to follow the steps
above, taking care to `git clone` it into
`~/go/src/github.com/abworrall` so golang will find it.

Caveats:
- the Go bindings of the API are very incomplete, but easy to extend
- the DNG SDK is in C++, so everything needs to be wrapped into plain old C
- there will be memory leaks, esp in the image handling


### Working with rendered data

The DNG development process will render the image into sRGB, doing
white balance correction, camera color correction, etc.

```go
import "github.com/abworrall/go-dng/pkg/dng"

func main() {
  n := dng.Negative{}
  //n.WhiteBalanceTemp = 5500; // Can override the white reference

  n.Load("my.dng")

  img := n.NewImage(dng.ImageFinalRender) // is an image.Image

  // See cmd/go-dng-validate/go-dng-validate.go for a longer example
}
```

## Working with Stage 3 data

The SDK provides access to image data at a few points in the
development process. Stage 1 is the raw sensor readings, stage 2 is
linearized but not-yet-demosaiced.

The stage 3 data is useful; it's been linearized and demosaiced, but
color corrections not yet applied - the stage 3 RGB values are in camera-native
space. You can also retrieve some color correction values from the
DNG, that account for the camera's development profile.

```go
import "github.com/abworrall/go-dng/pkg/dng"

func main() {
  n := dng.Negative{}
  n.Load("my.dng")

  img := n.NewImage(dng.ImageStage3) // is an image.Image

  // RGB representing a neutral white color, given the white reference point
  asShotNeutral := n.CameraWhite() // 

  // Matrix mapping camera native colors to 'profile connection space', CIEXYZ
  forwardMatrix := n.CameraToPCS()
}
```
