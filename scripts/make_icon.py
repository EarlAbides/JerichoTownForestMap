"""Generate app icons with no image library: raw PNG via zlib + struct."""
import math, pathlib, struct, zlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/"docs"; OUT.mkdir(exist_ok=True)

def png(path,size):
    BG=(0x10,0x1A,0x15); INK=(0xFF,0x7A,0x38); DIM=(0x2E,0x40,0x37)
    px=[[BG for _ in range(size)] for _ in range(size)]
    s=size/512.0
    def stroke(fn,t0,t1,w,col,steps=1400):
        for i in range(steps):
            t=t0+(t1-t0)*i/(steps-1)
            cx,cy=fn(t)
            r=int(w*s)
            for dy in range(-r,r+1):
                for dx in range(-r,r+1):
                    if dx*dx+dy*dy>r*r: continue
                    X,Y=int(cx*s)+dx,int(cy*s)+dy
                    if 0<=X<size and 0<=Y<size: px[Y][X]=col
    # contour-ish backdrop arcs
    for k in range(3):
        rad=150+k*62
        stroke(lambda t,r=rad:(256+r*math.cos(t),300+r*0.62*math.sin(t)),
               math.pi*1.06,math.pi*1.94,3,DIM)
    # the trail: an S-curve, echoing the rail alignment
    stroke(lambda t:(256+150*math.sin(t*1.5), 96+t*118), 0.0, 2.75, 15, INK)
    raw=b"".join(b"\x00"+b"".join(bytes(p) for p in row) for row in px)
    def chunk(tag,data):
        c=struct.pack(">I",len(data))+tag+data
        return c+struct.pack(">I",zlib.crc32(tag+data)&0xffffffff)
    out=(b"\x89PNG\r\n\x1a\n"
         +chunk(b"IHDR",struct.pack(">IIBBBBB",size,size,8,2,0,0,0))
         +chunk(b"IDAT",zlib.compress(raw,9))
         +chunk(b"IEND",b""))
    path.write_bytes(out)
    return len(out)

for sz,name in ((512,"icon-512.png"),(192,"icon-192.png"),(180,"icon-180.png")):
    n=png(OUT/name,sz)
    print(f"{name:14} {sz}x{sz}  {n/1024:.1f} KB")
