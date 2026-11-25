"""Build code-defined vector-style icons; Pillow is a build-only dependency."""
from pathlib import Path
from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent / 'assets'


def fluent_assets(dark=False):
    import math
    folder=ASSETS/'fluent'/('dark' if dark else '')
    folder.mkdir(parents=True,exist_ok=True)
    def surface(name,fill,border=None,radius=6):
        image=Image.new('RGBA',(128,128))
        d=ImageDraw.Draw(image)
        d.rounded_rectangle((2,2,125,125),radius*4,fill=fill,outline=border,width=4 if border else 1)
        image.resize((32,32),Image.Resampling.LANCZOS).save(folder/f'{name}.png')
    if dark:
        surface('panel','#252931','#3d4451',10)
        surface('nav','#20242c',None,8)
        surface('field-normal','#252931','#414956')
        surface('field-focus','#252931','#9daaf3')
        surface('field-disabled','#23272e','#363d48')
        palettes={
          'button':(('#2d323c','#444d5b'),('#353d49','#505c6d'),('#272d36','#424d5b'),('#252a32','#343c48')),
          'primary':(('#5365d2','#6173e1'),('#6172df','#6e81ed'),('#4658bc','#5265cf'),('#2e354c','#39415b')),
          'danger':(('#be4756','#d65b69'),('#cc5261','#e16b77'),('#a83a48','#c34e5b'),('#3b2b34','#4a343d')),
          'segment':(('#20242c',None),('#2b313b',None),('#303846',None),('#20242c',None)),
          'segment-selected':(('#343b4b','#515c73'),('#3b4456','#5a6781'),('#303949','#505d75'),('#252b36',None)),
        }
    else:
        surface('panel','white','#e3e6ec',10)
        surface('nav','#f1f3f7',None,8)
        surface('field-normal','white','#dfe3ea')
        surface('field-focus','white','#6b7bda')
        surface('field-disabled','#f1f3f6','#e4e7eb')
        palettes={
          'button':(('white','#dfe3e9'),('#f8f9fc','#d6dce5'),('#edf0f5','#d2d8e2'),('#f2f4f7','#e6e9ee')),
          'primary':(('#4657cc','#4657cc'),('#5264d7','#5264d7'),('#3949b8','#3949b8'),('#e5e8f4','#e5e8f4')),
          'danger':(('#b6414c','#b6414c'),('#c34b57','#c34b57'),('#9b3440','#9b3440'),('#f0e5e8','#f0e5e8')),
          'segment':(('#f1f3f7',None),('#e9edf4',None),('#e4e8f1',None),('#f1f3f7',None)),
          'segment-selected':(('white','#dfe4ed'),('white','#d8deeb'),('#f7f8fd','#d8deeb'),('#f1f3f7',None)),
        }
    for kind,colors in palettes.items():
        for state,(fill,border) in zip(('normal','hover','pressed','disabled'),colors):surface(f'{kind}-{state}',fill,border)
        surface(f'{kind}-focus',colors[0][0],'#a3aeef' if kind=='primary' else ('#dc8c95' if kind=='danger' else '#6b7bda'))
    colors=(('dark','#d4dae5'),('white','white'),('disabled','#737d8e'),('accent','#a8b4ff')) if dark else (('dark','#465064'),('white','white'),('disabled','#a9b0ba'),('accent','#4657cc'))
    for color_name,color in colors:
        for name in ('scan','stop','select','clear','preview','refresh','info','export','report','settings','copy','bookmark','close','left','right','trash','folder','up','cache','disk','down'):
            image=Image.new('RGBA',(96,96))
            d=ImageDraw.Draw(image)
            def point(p):return tuple(round(v*4) for v in p)
            def line(points):
                points=[point(p) for p in points]
                d.line(points,fill=color,width=8,joint='curve')
                for x,y in (points[0],points[-1]):d.ellipse((x-4,y-4,x+4,y+4),fill=color)
            def rect(box,r=2):d.rounded_rectangle(point(box),r*4,outline=color,width=8)
            def oval(box):d.ellipse(point(box),outline=color,width=8)
            def dot(x,y,r=1):d.ellipse(point((x-r,y-r,x+r,y+r)),fill=color)
            if name=='scan':oval((3,3,17,17));line(((16,16),(21,21)))
            elif name=='stop':rect((5,5,19,19))
            elif name=='select':rect((3,3,21,21),3);line(((7,12),(10,15),(17,8)))
            elif name=='clear':rect((3,3,21,21),3);line(((8,8),(16,16)));line(((8,16),(16,8)))
            elif name=='preview':line(((2,12),(7,7),(17,7),(22,12),(17,17),(7,17),(2,12)));oval((9,9,15,15))
            elif name=='refresh':d.arc(point((4,4,20,20)),40,310,fill=color,width=8);line(((15,3),(20,4),(19,9)))
            elif name=='info':oval((3,3,21,21));line(((12,11),(12,17)));dot(12,7)
            elif name=='export':line(((12,3),(12,15)));line(((8,7),(12,3),(16,7)));line(((4,13),(4,20),(20,20),(20,13)))
            elif name=='report':rect((5,2,19,22));line(((9,8),(15,8)));line(((9,12),(15,12)));line(((9,16),(13,16)))
            elif name=='settings':
                oval((6,6,18,18));oval((10,10,14,14))
                for angle in range(0,360,45):
                    a=math.radians(angle);line(((12+8*math.cos(a),12+8*math.sin(a)),(12+10*math.cos(a),12+10*math.sin(a))))
            elif name=='copy':line(((5,17),(3,17),(3,3),(17,3),(17,5)));rect((7,7,21,21))
            elif name=='bookmark':line(((6,3),(18,3),(18,21),(12,17),(6,21),(6,3)))
            elif name=='close':line(((6,6),(18,18)));line(((18,6),(6,18)))
            elif name=='left':line(((15,5),(8,12),(15,19)))
            elif name=='right':line(((9,5),(16,12),(9,19)))
            elif name=='trash':line(((4,6),(20,6)));rect((6,6,18,21));line(((9,6),(9,3),(15,3),(15,6)));line(((10,10),(10,17)));line(((14,10),(14,17)))
            elif name=='folder':line(((2,7),(2,20),(22,20),(22,7),(12,7),(9,4),(2,4),(2,7)))
            elif name=='up':line(((5,15),(12,8),(19,15)))
            elif name=='down':line(((6,9),(12,15),(18,9)))
            elif name=='cache':rect((4,3,20,10));rect((4,14,20,21))
            elif name=='disk':rect((3,7,21,20),3);line(((4,7),(7,3),(17,3),(20,7)));line(((7,15),(12,15)));dot(17,15)
            image.resize((16,16),Image.Resampling.LANCZOS).save(folder/f'{name}-{color_name}.png')


def logo():
    from PIL import ImageFilter
    image=Image.new('RGBA',(512,512))
    gradient=Image.new('RGBA',(512,512))
    gd=ImageDraw.Draw(gradient)
    for y in range(512):
        t=y/511
        color=tuple(round(a+(b-a)*t) for a,b in zip((93,111,235),(48,60,174)))+(255,)
        gd.line((0,y,512,y),fill=color)
    mask=Image.new('L',(512,512))
    ImageDraw.Draw(mask).rounded_rectangle((8,8,504,504),112,fill=255)
    image.paste(gradient,(0,0),mask)
    shadow=Image.new('RGBA',(512,512))
    ImageDraw.Draw(shadow).rounded_rectangle((100,215,416,392),36,fill=(15,24,101,75))
    image=Image.alpha_composite(image,shadow.filter(ImageFilter.GaussianBlur(12)))
    draw=ImageDraw.Draw(image)
    draw.polygon(((150,122),(362,122),(414,214),(98,214)),fill='#e5eaff')
    draw.rounded_rectangle((96,194,416,370),36,fill='#ffffff')
    draw.line((120,226,392,226),fill='#dde3fc',width=3)
    draw.rounded_rectangle((142,281,286,295),7,fill='#4657c8')
    draw.ellipse((328,280,344,296),fill='#4657c8')
    draw.ellipse((359,282,371,294),fill='#b7c1f6')
    return image


def main():
    ASSETS.mkdir(exist_ok=True)
    fluent_assets()
    fluent_assets(dark=True)
    image = logo()
    image.save(ASSETS / 'app.ico', sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    for n in (24, 32, 48, 64, 256):
        image.resize((n, n), Image.Resampling.LANCZOS).save(ASSETS / f'logo-{n}.png')
    (ASSETS / 'app.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x2="0" y2="1"><stop stop-color="#5d6feb"/><stop offset="1" stop-color="#303cae"/></linearGradient></defs><rect x="8" y="8" width="496" height="496" rx="112" fill="url(#a)"/><path d="M150 122h212l52 92H98Z" fill="#e5eaff"/><rect x="96" y="194" width="320" height="176" rx="36" fill="white"/><path d="M120 226h272" stroke="#dde3fc" stroke-width="3"/><rect x="142" y="281" width="144" height="14" rx="7" fill="#4657c8"/><circle cx="336" cy="288" r="8" fill="#4657c8"/><circle cx="365" cy="288" r="6" fill="#b7c1f6"/></svg>',encoding='utf-8')




if __name__ == '__main__':
    main()
