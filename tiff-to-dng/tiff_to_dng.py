'''Convert TIF file to DNG using Pillow/TiffImagePlugin'''

import argparse
import uuid
from fractions import Fraction
from PIL import Image, TiffImagePlugin

# Helper to convert float to rational tuple
def float_to_rational(f):
    '''adjust precision?'''
    # DNG spec suggests a denominator of 10000 for high precision
    frac = Fraction(f).limit_denominator(10000)
    return (frac.numerator, frac.denominator)

def main():
    '''Setup and run tiff-to-dng conversion'''
    parser = argparse.ArgumentParser(description='Convert a TIFF file to a DNG file.')
    parser.add_argument('input_file', type=str, help='The input TIFF file.')
    parser.add_argument('output_file', type=str, help='The output DNG file.')
    args = parser.parse_args()

    print(f"Input file: {args.input_file}")
    print(f"Output file: {args.output_file}")

    try:
        img = Image.open(args.input_file)
    except IOError:
        print(f"Error: Unable to open file {args.input_file}")
        return

    ifd = TiffImagePlugin.ImageFileDirectory_v2()

    # --- Image Data and Basic Info ---
    if img.mode == 'RGB':
        bits_per_sample = (8, 8, 8)
        samples_per_pixel = 3
    else:
        print(f"Error: Unsupported image mode '{img.mode}'. Only 'RGB' is supported.")
        return

    # --- Tag Types (from TiffTags.TYPES) ---
    BYTE = 1
    ASCII = 2
    SHORT = 3
    LONG = 4
    RATIONAL = 5
    SRATIONAL = 10
    UNDEFINED = 7

    # --- Populate IFD in strict numerical order ---

    # SubfileType (254)
    ifd[254] = 0
    ifd.tagtype[254] = LONG

    # ImageWidth (256)
    ifd[256] = img.width
    ifd.tagtype[256] = LONG

    # ImageHeight (257)
    ifd[257] = img.height
    ifd.tagtype[257] = LONG

    # BitsPerSample (258)
    ifd[258] = bits_per_sample
    ifd.tagtype[258] = SHORT

    # Compression (259)
    # 7 = JPEG. Pillow handles the compression when saving if you specify it.
    # We will try to save with JPEG compression.
    ifd[259] = 7
    ifd.tagtype[259] = SHORT

    # PhotometricInterpretation (262)
    # 32803 = LinearRaw
    ifd[262] = 32803
    ifd.tagtype[262] = SHORT

    # SamplesPerPixel (277)
    ifd[277] = samples_per_pixel
    ifd.tagtype[277] = SHORT

    # PlanarConfiguration (284)
    ifd[284] = 1 # Chunky
    ifd.tagtype[284] = SHORT
    
    # DNGVersion (50706)
    ifd[50706] = (1, 4, 0, 0)
    ifd.tagtype[50706] = BYTE

    # DNGBackwardVersion (50707)
    ifd[50707] = (1, 1, 0, 0)
    ifd.tagtype[50707] = BYTE

    # UniqueCameraModel (50708)
    ifd[50708] = "TIFF"
    ifd.tagtype[50708] = ASCII

    # ColorMatrix1 (50721) - From Nikon D90, as in the example DNG
    cm1_floats = [1.9625, -0.6108, -0.3414, -0.9787, 1.9161, 0.0335, 0.0286, -0.1407, 1.349]
    ifd[50721] = sum((float_to_rational(f) for f in cm1_floats), ())
    ifd.tagtype[50721] = SRATIONAL

    # AnalogBalance (50729)
    ifd[50729] = (1, 1, 1, 1, 1, 1) # (1/1, 1/1, 1/1)
    ifd.tagtype[50729] = RATIONAL

    # AsShotWhiteXY (50730)
    as_shot_floats = [0.3457, 0.3585]
    ifd[50730] = sum((float_to_rational(f) for f in as_shot_floats), ())
    ifd.tagtype[50730] = RATIONAL

    # BaselineExposure (50732)
    ifd[50732] = (0, 1)
    ifd.tagtype[50732] = SRATIONAL

    # BaselineNoise (50733)
    ifd[50733] = (1, 1)
    ifd.tagtype[50733] = RATIONAL

    # BaselineSharpness (50734)
    ifd[50734] = (1, 1)
    ifd.tagtype[50734] = RATIONAL

    # CalibrationIlluminant1 (50778)
    ifd[50778] = 0 # Unknown
    ifd.tagtype[50778] = SHORT

    # RawDataUniqueID (50781)
    ifd[50781] = uuid.uuid4().bytes
    ifd.tagtype[50781] = BYTE

    # BlackLevel (50714)
    ifd[50714] = (0, 1, 0, 1, 0, 1) # Three rationals of 0/1
    ifd.tagtype[50714] = RATIONAL

    # WhiteLevel (50717)
    ifd[50717] = (65535, 65535, 65535)
    ifd.tagtype[50717] = LONG

    # DefaultScale (50780)
    ifd[50780] = (1, 1, 1, 1)
    ifd.tagtype[50780] = RATIONAL

    # DefaultCropOrigin (50718)
    ifd[50718] = (0, 1, 0, 1)
    ifd.tagtype[50718] = RATIONAL

    # DefaultCropSize (50719)
    ifd[50719] = (img.width, 1, img.height, 1)
    ifd.tagtype[50719] = RATIONAL

    # ActiveArea (50829)
    ifd[50829] = (0, 0, img.height, img.width) # top, left, bottom, right
    ifd.tagtype[50829] = LONG

    # ShadowScale (50970)
    ifd[50970] = (1, 1)
    ifd.tagtype[50970] = RATIONAL

    print("Attempting to save DNG with comprehensive tags...")
    try:
        img.save(
            args.output_file,
            "TIFF",
            tiffinfo=ifd,
            compression="jpeg" # Attempt to use JPEG compression
        )
        print(f"Successfully created a file at {args.output_file}")
    except Exception as e:
        print(f"Error saving DNG: {e}")

if __name__ == '__main__':
    main()
