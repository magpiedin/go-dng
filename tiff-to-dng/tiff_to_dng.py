'''Convert TIF file to DNG using Pillow/TiffImagePlugin'''

import argparse
import uuid
from fractions import Fraction
from PIL import Image, TiffImagePlugin

def main():
    '''Setup and run tiff-to-dng conversion'''
    parser = argparse.ArgumentParser(description='Convert a TIFF file to a DNG file.')
    parser.add_argument('input_file', type=str, help='The input TIFF file.')
    parser.add_argument('output_file', type=str, help='The output DNG file.')
    args = parser.parse_args()

    print(f"Input file: {args.input_file}")
    print(f"Output file: {args.output_file}")

    try:
        source_img = Image.open(args.input_file)
    except IOError:
        print(f"Error: Unable to open file {args.input_file}")
        return

    # --- Isolate Pixel Data ---
    if source_img.mode != 'RGB':
        print(f"Error: Unsupported image mode '{source_img.mode}'. Only 'RGB' is supported.")
        return
    pixel_data = list(source_img.getdata())
    img = Image.new(source_img.mode, source_img.size)
    img.putdata(pixel_data)

    # --- IFD and Tag Setup ---
    ifd = TiffImagePlugin.ImageFileDirectory_v2()

    BYTE = 1; ASCII = 2; SHORT = 3; LONG = 4; RATIONAL = 5; SRATIONAL = 10

    # --- Populate IFD in strict numerical order ---
    ifd[254] = 0; ifd.tagtype[254] = LONG                             # SubfileType
    ifd[256] = img.width; ifd.tagtype[256] = LONG                      # ImageWidth
    ifd[257] = img.height; ifd.tagtype[257] = LONG                     # ImageHeight
    ifd[258] = (8, 8, 8); ifd.tagtype[258] = SHORT                     # BitsPerSample
    ifd[259] = 7; ifd.tagtype[259] = SHORT                             # Compression (7=JPEG)
    ifd[262] = 32803; ifd.tagtype[262] = SHORT                         # PhotometricInterpretation (LinearRaw)
    ifd[274] = 1; ifd.tagtype[274] = SHORT                             # Orientation (1 = Normal)
    ifd[277] = 3; ifd.tagtype[277] = SHORT                             # SamplesPerPixel
    ifd[284] = 1; ifd.tagtype[284] = SHORT                             # PlanarConfiguration (Chunky)

    # --- Tiling Tags - CRITICAL for JPEG Compression ---
    ifd[322] = 192; ifd.tagtype[322] = LONG                            # TileWidth
    ifd[323] = 224; ifd.tagtype[323] = LONG                            # TileLength

    # --- DNG-specific tags ---
    ifd[50706] = b'\x01\x04\x00\x00'; ifd.tagtype[50706] = BYTE        # DNGVersion
    ifd[50707] = b'\x01\x01\x00\x00'; ifd.tagtype[50707] = BYTE        # DNGBackwardVersion
    ifd[50708] = "TIFF"; ifd.tagtype[50708] = ASCII                    # UniqueCameraModel

    # Using a simplified gamma 2.2 table. A more accurate one could be used.
    ifd[50712] = tuple(int(round((i/255.0)**(2.2) * 65535)) for i in range(256))
    ifd.tagtype[50712] = SHORT                                        # LinearizationTable

    ifd[50714] = (Fraction(0,1), Fraction(0,1), Fraction(0,1)); ifd.tagtype[50714] = RATIONAL
    ifd[50717] = (255, 255, 255); ifd.tagtype[50717] = SHORT

    cm1_floats = [1.9625, -0.6108, -0.3414, -0.9787, 1.9161, 0.0335, 0.0286, -0.1407, 1.349]
    ifd[50721] = tuple(Fraction(f).limit_denominator(10000) for f in cm1_floats)
    ifd.tagtype[50721] = SRATIONAL

    ifd[50729] = (Fraction(1, 1), Fraction(1, 1), Fraction(1, 1)); ifd.tagtype[50729] = RATIONAL
    as_shot_floats = [0.3457, 0.3585]
    ifd[50730] = tuple(Fraction(f).limit_denominator(10000) for f in as_shot_floats)
    ifd.tagtype[50730] = RATIONAL

    ifd[50732] = Fraction(0, 1); ifd.tagtype[50732] = SRATIONAL
    ifd[50734] = Fraction(1, 1); ifd.tagtype[50734] = SRATIONAL
    ifd[50781] = uuid.uuid4().bytes; ifd.tagtype[50781] = BYTE
    ifd[50829] = (0, 0, img.height, img.width); ifd.tagtype[50829] = LONG
    ifd[50970] = Fraction(1, 1); ifd.tagtype[50970] = RATIONAL

    print("Attempting to save Tiled, JPEG-Compressed DNG...")
    try:
        img.save(
            args.output_file,
            "TIFF",
            tiffinfo=ifd,
            compression='jpeg',
            exif=b'' # Prevent copying any source EXIF data
        )
        print(f"Successfully created a file at {args.output_file}")
    except Exception as e:
        print(f"Error saving DNG: {e}")

if __name__ == '__main__':
    main()
