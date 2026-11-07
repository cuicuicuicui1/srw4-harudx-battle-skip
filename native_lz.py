"""Independent decode of the emitted 80F93D byte/bit/backreference format.
Returns consumed source length and output; malformed streams are bounded.
"""
class NativeLZError(ValueError):pass
def decode(rom,start,max_output=0x4000,max_source=0x10000,history=None):
 pos=start;flags=0;remaining=0;out=bytearray();commands=[]
 def byte():
  nonlocal pos
  if pos>=len(rom) or pos-start>=max_source:raise NativeLZError('source bound')
  v=rom[pos];pos+=1;return v
 def bit():
  nonlocal flags,remaining
  if not remaining:flags=byte();remaining=8
  b=(flags>>7)&1;flags=(flags<<1)&255;remaining-=1;return b
 def copy(offset,n):
  if len(out)+n>max_output:raise NativeLZError('output bound')
  for _ in range(n):
   i=len(out)+offset
   if i<0:
    if history is None or i < -len(history):raise NativeLZError('reference before decoded image')
    out.append(history[i])
   else:out.append(out[i])
 while True:
  if bit():
   if len(out)>=max_output:raise NativeLZError('output bound')
   out.append(byte());commands.append('literal')
  elif not bit():
   n=(bit()<<1)|bit();offset=byte()-256;copy(offset,n+2);commands.append('short')
  else:
   packed=(byte()<<8)|byte();offset=(packed>>3)|0xE000;offset-=65536
   n=packed&7
   if n:n+=2
   else:
    n=byte()
    if not n:return {'start':start,'end':pos,'source_bytes':pos-start,'output':bytes(out),'commands':len(commands),'terminator_end':pos}
    n+=1
   copy(offset,n);commands.append('long')
