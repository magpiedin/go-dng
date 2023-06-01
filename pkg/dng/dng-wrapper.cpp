#include <stdio.h>

#include "dng_color_space.h"
#include "dng_color_spec.h"
#include "dng_date_time.h"
#include "dng_exceptions.h"
#include "dng_file_stream.h"
#include "dng_globals.h"
#include "dng_host.h"
#include "dng_ifd.h"
#include "dng_image_writer.h"
#include "dng_info.h"
#include "dng_linearization_info.h"
#include "dng_mosaic_info.h"
#include "dng_negative.h"
#include "dng_parse_utils.h"
#include "dng_preview.h"
#include "dng_rect.h"
#include "dng_render.h"
#include "dng_simple_image.h"
#include "dng_tag_codes.h"
#include "dng_tag_types.h"
#include "dng_tag_values.h"
#include "dng_temperature.h"

#include "dng-wrapper.h"

// Helper functions just for this file
dng_negative*     AsNeg(CNegative *cneg)       { return reinterpret_cast<dng_negative*>(cneg->negative); }
dng_color_spec*   AsColorSpec(CNegative *cneg) { return reinterpret_cast<dng_color_spec*>(cneg->colorspec); }
dng_image*        AsImage(CNegative *cneg)     { return reinterpret_cast<dng_image*>(cneg->image_final); }
dng_pixel_buffer* AsPixBuf(CNegative *cneg)    { return reinterpret_cast<dng_pixel_buffer*>(cneg->pixelbuffer); }

// Convert C++ objects to our POD C types, so we can return them into Golang.
CURat AsCUrat(dng_urational v) {
  CURat ret;
  ret.v[0] = (uint32_t)v.n;
  ret.v[1] = (uint32_t)v.d;
  return ret;
}
CURat AsCUratFromSRat(dng_srational v) {
  CURat ret;
  ret.v[0] = (uint32_t)v.n;
  ret.v[1] = (uint32_t)v.d;
  return ret;
}
CVec3 AsCVec3(dng_vector v) {
  CVec3 ret;
  if (v.Count() == 3) {
    ret.v[0] = v[0];
    ret.v[1] = v[1];
    ret.v[2] = v[2];
  }
  return ret;
}
CMat3 AsCMat3(dng_matrix m) {
  CMat3 ret;
  if (m.Rows() == 3 && m.Cols()==3) {
    int x, y;
    for (x=0; x<3; x++) {
      for (y=0; y<3; y++) {
        ret.v[x + y*3] = m[y][x]; // First index in dng_matrix is the row
      }
    }
  }
  return ret;
}
CRect AsCRect(dng_rect r) {
  CRect ret;
  ret.v[0] = r.TL().h;  // Top-Left is origin
  ret.v[1] = r.TL().v;
  ret.v[2] = r.BR().h;
  ret.v[3] = r.BR().v;
  return ret;
}

//// The simple C API we expose up into cgo
const char* GO_OriginalRawFileName(CNegative *cneg) { return AsNeg(cneg)->OriginalRawFileName().Get(); }
CVec3       GO_CameraWhite(CNegative *cneg)         { return AsCVec3( AsColorSpec(cneg)->CameraWhite() ); }
CMat3       GO_CameraToPCS(CNegative *cneg)         { return AsCMat3( AsColorSpec(cneg)->CameraToPCS() ); }
CRect       GO_Bounds(CNegative *cneg)              { return AsCRect( AsNeg(cneg)->Stage3Image()->Size() ); }

CURat    GO_ExifExposureTime(CNegative *cneg) { return AsCUrat( AsNeg(cneg)->Metadata().GetExif()->fExposureTime ); }
CURat    GO_ExifFNumber(CNegative *cneg)      { return AsCUrat( AsNeg(cneg)->Metadata().GetExif()->fFNumber ); }
uint32_t GO_ExifISO(CNegative *cneg) {
  dng_exif *exif = AsNeg(cneg)->Metadata().GetExif();
  return exif->fISOSpeedRatings[exif->fISOSpeed];
}

dng_pixel_buffer *makePixelBuffer(CNegative *cneg, int kind)
{
  // We want (dng_simple_image)s, as they have prebuilt (dng_pixel_buffer)s.
  // Creating a pixel buffer by hand, using a regular image, needs an
  // internal adobe helper; but luckily we don't have to, because the API
  // creates dng_simple_images under the hood and we can just cast them back.
  dng_simple_image *s_img;
  
  switch (kind) {
  case ImageStage3:
    s_img = (dng_simple_image *)(AsNeg(cneg)->Stage3Image()); // cast is safe for the StageNImage()s
    break;

  default:
  case ImageUndefined:    // If undefined, default to FinalRender
  case ImageFinalRender:
    s_img = (dng_simple_image *)(AsImage(cneg)); // cast is safe for output of render.Render()
    break;
  }

  dng_pixel_buffer *buf = new dng_pixel_buffer;
  s_img->GetPixelBuffer(*buf);

  return buf;
}

CNegative *GO_Make(const char *filename, CNegativeArgs args)
{
  CNegative *cneg = (CNegative *)malloc(sizeof(CNegative));

  //printf ("Loading \"%s\"...\n", filename);

  // globals in dng_validate.cpp
  static int32 gMosaicPlane = -1;
  static const dng_color_space *gFinalSpace = &dng_space_sRGB::Get();
  static uint32 gFinalPixelType = ttByte; // 8 bits per channel

  if (args.verbose > 0) {
    gVerbose = true;
    printf ("\n>>>>>>> Start of Verbose SDK output >>>>>>>>\n");
  }

  dng_host host;
  dng_info info;
  dng_file_stream stream (filename);

  //host.SetWantsPreserveStage2(true); // If we ever want to do anything with stage2 data, set this

  // These are the main objects we instantiate and store
  dng_negative* negative;
  dng_image* image_final;
  dng_color_spec *colorspec;
  
  try {
    info.Parse (host, stream);
    info.PostParse (host);
    if (!info.IsValidDNG ()) {
      throw "Bad file, IsValidDNG() failed";
    }

    negative = host.Make_dng_negative();

    negative->Parse (host, stream, info);
    negative->PostParse (host, stream, info);
    negative->ReadStage1Image (host, stream, info);
    negative->SynchronizeMetadata ();

    // By default, the negative will get cropped (6 pixels each edge) during render.Render(); prevent that.
    dng_rect bounds = negative->Stage1Image()->Size();
    negative->SetDefaultCropSize(bounds.r, bounds.b);
    
    negative->BuildStage2Image (host);			 
    negative->BuildStage3Image (host, gMosaicPlane); // builds a dng_simple_image under the hood

    if (args.verbose > 0) {
      printf ("<<<<<<<< End of Verbose SDK output <<<<<<<<\n\n");
    }
    //printf ("- completed stage3 building\n");

    // Any color spec requires a white reference point, so set that up as best we can
    // Cloned from dng_render.cpp:867-902
    dng_camera_profile_id id; // As id.IsValid()==false, this empty ID maps to the default (first) profile
    dng_temperature temp;
    colorspec = negative->MakeColorSpec (id);
    if (negative->HasCameraNeutral()) {
      temp = dng_temperature(colorspec->NeutralToXY(negative->CameraNeutral()));
    } else if (negative->HasCameraWhiteXY()) {
      temp = dng_temperature(negative->CameraWhiteXY());
    } else {
      temp = dng_temperature(D55_xy_coord());
    }

    if (args.white_balance_temp > 0) {
      temp.SetTemperature((double)args.white_balance_temp); // Override temp here
      printf ("- created color_spec (temp=%.0fK, override)\n", temp.Temperature());
    } else {
      //printf ("- created color_spec (temp=%.0fK, as per DNG)\n", temp.Temperature());
    }
    colorspec->SetWhiteXY(temp.Get_xy_coord());

    dng_render render (host, *negative);
    render.SetWhiteXY (colorspec->WhiteXY());
    render.SetFinalSpace (*gFinalSpace);
    render.SetFinalPixelType (gFinalPixelType);
    if (host.MinimumSize ()) {
      dng_point stage3Size = negative->Stage3Image()->Size ();
      render.SetMaximumSize (Max_uint32 (stage3Size.v, stage3Size.h));
    }

    image_final = render.Render(); // builds a dng_simple_image under the hood
    image_final->Rotate (negative->Orientation());
    //printf ("- completed final rendering\n");
    
  } catch (const dng_exception &except) {
    printf ("Failed to load and process DNG, SDK errorcode: %d\n", except.ErrorCode());
    return NULL;
  } catch (char *str) {
    printf ("Failed to load and process DNG, err: %s\n", str);
    return NULL;
  } catch (...) {
    printf ("Failed to load and process DNG, unknown exception\n");
    return NULL;
  }

  //printf ("- loading complete\n");

  cneg->negative    = negative;
  cneg->image_final = image_final;
  cneg->colorspec   = colorspec;
  cneg->pixelbuffer = makePixelBuffer(cneg, args.image_kind);
  
  return cneg;
}

void GO_Free(CNegative *cneg)
{
  if (cneg->negative != NULL) {
    free(AsNeg(cneg));
  }
  if (cneg->colorspec != NULL) {
    free(AsColorSpec(cneg));
  }
  if (cneg->image_final != NULL) {
    free(AsImage(cneg));
  }
  // cneg->pixelbuffer ?
  free(cneg);
}

// This function populates `dst` with three RGB uint16s, each scaled to the range [0, 0xFFFF].
void GO_GetPixelRGB(CNegative *cneg, int x, int y, uint16_t *dst)
{
  dng_pixel_buffer *buf = AsPixBuf(cneg);

  // Sanity checks
  if (buf == NULL) {
    throw "GO_PixelBuffer_GetPixel: v==NULL";

  } else if (buf->ConstPixel(y, x) == NULL) {
    throw "GO_PixelBuffer_GetPixel: buf->ConstPixel()==NULL";

  } else if ((buf->fPixelType == ttShort && buf->fPixelSize != 2) ||
             (buf->fPixelType == ttByte && buf->fPixelSize != 1)) {
    // Assert that shorts are 16 bytes, etc
    throw "GO_PixelBuffer_GetPixel: unexpected sizes for ttShort etc";

  } else if (buf->fPlanes != 3) {
    throw "GO_PixelBuffer_GetPixel: wrong number of color planes";
  }
  
  // The DNG API expects us to handle a range of types and sizes, and
  // figure out how to cast them - see the enum at the top of
  // dng_tag_types. We only handle uint16 and uint8.
  const uint16 *sPtrA16; // ttShort, 'short unsigned int', uint16, what we see in Stage3 images
  const uint8 *sPtrA8;   // ttByte, what we see in final rendered sRGB output
  void* tmp = (void *)buf->ConstPixel(y, x); // args are (row, col)
  switch (buf->fPixelType) {
  case ttShort:
    sPtrA16 = buf->ConstPixel_uint16(y, x);
    dst[0] = *sPtrA16;
    dst[1] = *(sPtrA16 +   buf->fPlaneStep);
    dst[2] = *(sPtrA16 + 2*buf->fPlaneStep);
    break;

  case ttByte:
    sPtrA8 = buf->ConstPixel_uint8(y, x);
    dst[0] = *sPtrA8;
    dst[1] = *(sPtrA8 +   buf->fPlaneStep);
    dst[2] = *(sPtrA8 + 2*buf->fPlaneStep);
    break;

  default:
    throw "GO_PixelBuffer_GetPixel: unhandled pixel type slipped through sanity checks";
  }

  // Rescale the values to the range [0,0xFFFF] if needed - e,g, ttByte is [0,0xFF]
  int mult = 0xFFFF / buf->PixelRange();
  if (mult != 1) {
    dst[0] *= mult;
    dst[1] *= mult;
    dst[2] *= mult;
  }
}
