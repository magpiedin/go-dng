'''Convert TIF file to DNG using Pillow/TiffImagePlugin'''

import argparse
import uuid
from fractions import Fraction
import numpy as np
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

    # --- Image Data Linearization ---
    # This is the critical step. The source sRGB data must be converted to linear.
    if source_img.mode != 'RGB':
        print(f"Error: Unsupported image mode '{source_img.mode}'. Only 'RGB' is supported.")
        return

    # Convert image to numpy array, normalize to 0-1 float
    srgb_data = np.array(source_img, dtype=np.float32) / 255.0

    # Apply gamma correction (sRGB to linear)
    # Using a simple gamma of 2.2 as an approximation.
    linear_data = np.power(srgb_data, 2.2)

    # Scale to 16-bit integer range
    uint16_data = (linear_data * 65535).astype(np.uint16)
    
    # Create a new Pillow image from the 16-bit linear data
    img = Image.fromarray(uint16_data, 'RGB')

    # --- IFD and Tag Setup ---
    ifd = TiffImagePlugin.ImageFileDirectory_v2()

    BYTE = 1; ASCII = 2; SHORT = 3; LONG = 4; RATIONAL = 5; SRATIONAL = 10

    # --- Populate IFD in strict numerical order ---
    ifd[254] = 0; ifd.tagtype[254] = LONG                             # SubfileType
    ifd[256] = img.width; ifd.tagtype[256] = LONG                      # ImageWidth
    ifd[257] = img.height; ifd.tagtype[257] = LONG                     # ImageHeight
    ifd[258] = (16, 16, 16); ifd.tagtype[258] = SHORT                  # BitsPerSample (now 16-bit)
    ifd[259] = 1; ifd.tagtype[259] = SHORT                             # Compression (1 = Uncompressed)
    ifd[262] = 32803; ifd.tagtype[262] = SHORT                         # PhotometricInterpretation (LinearRaw)
    ifd[274] = 1; ifd.tagtype[274] = SHORT                             # Orientation (1 = Normal)
    ifd[277] = 3; ifd.tagtype[277] = SHORT                             # SamplesPerPixel
    ifd[284] = 1; ifd.tagtype[284] = SHORT                             # PlanarConfiguration (Chunky)

    # --- DNG-specific tags ---
    ifd[50706] = b'\x01\x04\x00\x00'; ifd.tagtype[50706] = BYTE        # DNGVersion
    ifd[50707] = b'\x01\x01\x00\x00'; ifd.tagtype[50707] = BYTE        # DNGBackwardVersion
    ifd[50708] = "TIFF"; ifd.tagtype[50708] = ASCII                    # UniqueCameraModel

    # Using Fraction objects for RATIONAL/SRATIONAL tags
    cm1_floats = [1.9625, -0.6108, -0.3414, -0.9787, 1.9161, 0.0335, 0.0286, -0.1407, 1.349]
    ifd[50721] = tuple(Fraction(f).limit_denominator(10000) for f in cm1_floats)
    ifd.tagtype[50721] = SRATIONAL

    # For now, removing tags that caused validation warnings to focus on the CFA error.
    # ifd[50730] = ... # AsShotWhiteXY
    # ifd[50732] = ... # BaselineExposure

    # Correcting type for BaselineSharpness
    ifd[50734] = Fraction(1, 1); ifd.tagtype[50734] = SRATIONAL

    ifd[50781] = uuid.uuid4().bytes; ifd.tagtype[50781] = BYTE         # RawDataUniqueID
    ifd[50714] = (Fraction(0,1), Fraction(0,1), Fraction(0,1)); ifd.tagtype[50714] = RATIONAL # BlackLevel
    ifd[50717] = (65535, 65535, 65535); ifd.tagtype[50717] = LONG      # WhiteLevel (now 16-bit)

    ifd[50829] = (0, 0, img.height, img.width); ifd.tagtype[50829] = LONG # ActiveArea

    print("Attempting to save DNG with linearized data...")
    try:
        img.save(
            args.output_file,
            "TIFF",
            tiffinfo=ifd
        )
        print(f"Successfully created a file at {args.output_file}")
    except Exception as e:
        print(f"Error saving DNG: {e}")

if __name__ == '__main__':
    main()
