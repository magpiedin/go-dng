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

    # Create a new blank image and paste the source pixels.
    # This is a crucial step to prevent Pillow from copying any existing,
    # unwanted metadata from the source TIFF file.
    img = Image.new(source_img.mode, source_img.size)
    img.paste(source_img)

    ifd = TiffImagePlugin.ImageFileDirectory_v2()

    if img.mode == 'RGB':
        bits_per_sample = (8, 8, 8)
        samples_per_pixel = 3
    else:
        print(f"Error: Unsupported image mode '{img.mode}'.")
        return

    BYTE = 1; ASCII = 2; SHORT = 3; LONG = 4; RATIONAL = 5; SRATIONAL = 10

    # --- Populate IFD in strict numerical order ---
    ifd[254] = 0; ifd.tagtype[254] = LONG
    ifd[256] = img.width; ifd.tagtype[256] = LONG
    ifd[257] = img.height; ifd.tagtype[257] = LONG
    ifd[258] = bits_per_sample; ifd.tagtype[258] = SHORT
    ifd[259] = 1; ifd.tagtype[259] = SHORT
    ifd[262] = 32803; ifd.tagtype[262] = SHORT
    ifd[277] = samples_per_pixel; ifd.tagtype[277] = SHORT
    ifd[284] = 1; ifd.tagtype[284] = SHORT
    
    ifd[50706] = b'\x01\x04\x00\x00'; ifd.tagtype[50706] = BYTE
    ifd[50707] = b'\x01\x01\x00\x00'; ifd.tagtype[50707] = BYTE
    ifd[50708] = "TIFF"; ifd.tagtype[50708] = ASCII
    
    # CRITICAL FIX: RATIONAL/SRATIONAL tags expect Fraction objects, not tuples.
    cm1_floats = [1.9625, -0.6108, -0.3414, -0.9787, 1.9161, 0.0335, 0.0286, -0.1407, 1.349]
    ifd[50721] = tuple(Fraction(f).limit_denominator(10000) for f in cm1_floats)
    ifd.tagtype[50721] = SRATIONAL
    
    ifd[50729] = (Fraction(1, 1), Fraction(1, 1), Fraction(1, 1)); ifd.tagtype[50729] = RATIONAL
    
    as_shot_floats = [0.3457, 0.3585]
    ifd[50730] = tuple(Fraction(f).limit_denominator(10000) for f in as_shot_floats)
    ifd.tagtype[50730] = RATIONAL

    ifd[50732] = Fraction(0, 1); ifd.tagtype[50732] = SRATIONAL
    ifd[50733] = Fraction(1, 1); ifd.tagtype[50733] = RATIONAL
    ifd[50734] = Fraction(1, 1); ifd.tagtype[50734] = RATIONAL

    ifd[50778] = 0; ifd.tagtype[50778] = SHORT
    ifd[50781] = uuid.uuid4().bytes; ifd.tagtype[50781] = BYTE

    ifd[50714] = (Fraction(0,1), Fraction(0,1), Fraction(0,1)); ifd.tagtype[50714] = RATIONAL
    ifd[50717] = (255, 255, 255); ifd.tagtype[50717] = SHORT

    ifd[50780] = (Fraction(1, 1), Fraction(1, 1)); ifd.tagtype[50780] = RATIONAL
    ifd[50718] = (Fraction(0, 1), Fraction(0, 1)); ifd.tagtype[50718] = RATIONAL
    ifd[50719] = (Fraction(img.width, 1), Fraction(img.height, 1)); ifd.tagtype[50719] = RATIONAL

    ifd[50829] = (0, 0, img.height, img.width); ifd.tagtype[50829] = LONG
    ifd[50970] = Fraction(1, 1); ifd.tagtype[50970] = RATIONAL

    print("Attempting to save DNG with final tag format...")
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
