"""Find a display-only content rectangle; original pixels/word boxes stay intact."""
from PIL import Image, ImageFilter


def content_view(image, protected_boxes=()):
    width,height=image.size
    small=image.convert('L')
    small.thumbnail((1600,1600))
    # Ignore faint scanner paper texture and isolated speckles. Median filtering
    # is only used for detection, never for the image displayed by the reader.
    ink=small.point(lambda p:255 if p<200 else 0).filter(ImageFilter.MedianFilter(3))
    columns=[sum(ink.crop((x,0,x+1,ink.height)).histogram()[1:]) for x in range(ink.width)]
    rows=[sum(ink.crop((0,y,ink.width,y+1)).histogram()[1:]) for y in range(ink.height)]
    xs=[x for x,n in enumerate(columns) if n>=4]
    ys=[y for y,n in enumerate(rows) if n>=4]
    if xs and ys:
        bounds=[min(xs)*width/ink.width,min(ys)*height/ink.height,
                (max(xs)+1)*width/ink.width,(max(ys)+1)*height/ink.height]
    else:
        bounds=[width,height,0,0]
    # Retain all OCR regions (including English/pinyin) and every tappable box,
    # even if the raster threshold misses faint text.
    for x,y,w,h in protected_boxes:
        bounds=[min(bounds[0],x),min(bounds[1],y),max(bounds[2],x+w),max(bounds[3],y+h)]
    if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:return [0,0,width,height]
    padding=max(24,round(min(width,height)*.012))
    left=max(0,int(bounds[0])-padding);top=max(0,int(bounds[1])-padding)
    right=min(width,int(bounds[2]+.999)+padding);bottom=min(height,int(bounds[3]+.999)+padding)
    return [left,top,right-left,bottom-top]
