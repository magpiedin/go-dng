'''Convert TIF file to DNG'''

import os
import xml.etree.ElementTree as ET
import argparse
from datetime import datetime
import numpy as np
from PIL import Image
from pidng.core import RAW2DNG
from pidng.dng import DNGTags, Tag, Type
from pidng.defs import DNGVersion, PhotometricInterpretation

# Manually define the ICCProfile tag as it's missing from pidng
ICCProfileTag = (34675, Type.Undefined)
Tag.ICCProfile = ICCProfileTag # Add it to the Tag class for convenience

def main():
    '''Setup and run tiff-to-dng conversion'''
    parser = argparse.ArgumentParser(description='Convert a TIFF file to a DNG file.')
    parser.add_argument('input_file', type=str, help='The input TIFF file.')
    parser.add_argument('output_file', type=str, help='The output DNG file.')
    args = parser.parse_args()

    print(f"Input file: {args.input_file}")
    print(f"Output file: {args.output_file}")

    # Open the TIFF image
    try:
        image = Image.open(args.input_file)
    except IOError:
        print(f"Error: Unable to open file {args.input_file}")
        return

    # Convert image to numpy array and ensure it's uint16 for pidng
    image_data = np.asarray(image)
    
    if image_data.dtype == np.uint8:
        image_data = (image_data.astype(np.uint16)) * 257
    elif image_data.dtype != np.uint16:
        image_data = image_data.astype(np.uint16)

    bits_per_sample = 16
    white_level = 65535
    samples = len(image.getbands())
    
    # Extract metadata from XMP first, so we can set all tags in order
    icc_profile = list(image.info['icc_profile']) if 'icc_profile' in image.info and image.info['icc_profile'] else None
    xmp_datetime = None
    xmp_datetime_original = None
    xmp_profile_name = None

    if 'xmp' in image.info:
        xmp_data = image.info['xmp']
        xmp_str = xmp_data.decode('utf-8', 'ignore')
        xml_start = xmp_str.find('<x:xmpmeta')
        if xml_start != -1:
            xmp_str = xmp_str[xml_start:]
            try:
                root = ET.fromstring(xmp_str)
                ns = {
                    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                    'xmp': 'http://ns.adobe.com/xap/1.0/',
                    'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
                }

                def format_date(date_str):
                    try:
                        if '+' in date_str or ('-' in date_str and date_str.rfind('-') > 7):
                            dt_obj = datetime.fromisoformat(date_str)
                        else:
                            dt_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                        return dt_obj.strftime("%Y:%m:%d %H:%M:%S")
                    except (ValueError, TypeError):
                        try:
                            dt_obj = datetime.strptime(date_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                            return dt_obj.strftime("%Y:%m:%d %H:%M:%S")
                        except:
                            return None

                modify_date = root.find('.//xmp:ModifyDate', ns)
                if modify_date is not None:
                    xmp_datetime = format_date(modify_date.text)

                create_date = root.find('.//xmp:CreateDate', ns)
                if create_date is not None:
                    xmp_datetime_original = format_date(create_date.text)

                camera_profile = root.find('.//crs:CameraProfile', ns)
                if camera_profile is not None:
                    xmp_profile_name = camera_profile.text

            except ET.ParseError as e:
                print(f"Error parsing XMP data: {e}")

    # Create DNG tags in ascending numerical order, as required by the spec
    tags = DNGTags()
    
    tags.set(Tag.NewSubfileType, 0)                                      # 254
    tags.set(Tag.ImageWidth, image.width)                               # 256
    tags.set(Tag.ImageLength, image.height)                             # 257
    tags.set(Tag.BitsPerSample, bits_per_sample)                        # 258
    tags.set(Tag.PhotometricInterpretation, PhotometricInterpretation.Linear_Raw) # 262
    tags.set(Tag.SamplesPerPixel, samples)                              # 277
    tags.set(Tag.Software, "tiff-to-dng converter")                     # 305
    tags.set(Tag.DateTime, xmp_datetime or datetime.now().strftime("%Y:%m:%d %H:%M:%S")) # 306
    
    if icc_profile:
        tags.set(Tag.ICCProfile, icc_profile)                           # 34675
        
    if xmp_datetime_original:
        tags.set(Tag.DateTimeOriginal, xmp_datetime_original)           # 36867

    tags.set(Tag.DNGVersion, DNGVersion.V1_4)                           # 50706
    tags.set(Tag.DNGBackwardVersion, DNGVersion.V1_0)                   # 50707
    tags.set(Tag.UniqueCameraModel, "TIFF")                             # 50708
    tags.set(Tag.BlackLevel, [0] * samples)                             # 50714
    tags.set(Tag.WhiteLevel, [white_level] * samples)                   # 50717
    
    if xmp_profile_name:
        tags.set(Tag.ProfileName, xmp_profile_name)                     # 50931

    # Use pidng to convert to DNG
    try:
        dng = RAW2DNG()
        # The pidng library seems to ignore the output_dir, so we pass an empty one
        # and provide the full path to the convert method.
        dng.options(tags, "")
        dng.convert(image_data, filename=args.output_file)
        print(f"Successfully converted {args.input_file} to {args.output_file}")
    except Exception as e:
        print(f"Error converting to DNG: {e}")

if __name__ == '__main__':
    main()