local out=assert(os.getenv('PROBE_OUT'))
local path=assert(os.getenv('PROBE_STATE'))
local key=assert(os.getenv('PROBE_KEY'))
local first=assert(tonumber(os.getenv('PROBE_FIRST')))
local last=assert(tonumber(os.getenv('PROBE_LAST')))
local m=emu.memType.snesMemory
local n=0;local loaded=false;local loadAt=0;local returned=false;local due=nil
local acknowledge=os.getenv('PROBE_ACK')=='1'
local save=os.getenv('PROBE_SAVE')=='1'
local file=assert(io.open(out..'/trace.log','w'))
local function p(s)file:write(s..'\n');file:flush()end
local function u(a)return emu.read(a,m)|(emu.read(a+1,m)<<8)end
local function u24(a)return u(a)|(emu.read(a+2,m)<<16)end
local function dump(name,kind,size)
 local t={};for a=0,size-1 do t[#t+1]=string.char(emu.read(a,kind)&255)end
 local f=assert(io.open(out..'/'..name,'wb'));f:write(table.concat(t));f:close()
end
local function shot(name)
 local f=assert(io.open(out..'/'..name..'.png','wb'));f:write(emu.takeScreenshot());f:close()
 dump(name..'.ram',emu.memType.snesWorkRam,0x20000)
end
emu.addMemoryCallback(function()
 if n>=100 and not loaded then
  loaded=true;loadAt=n
  local f=assert(io.open(path,'rb'));local bytes=f:read('*a');f:close();assert(emu.loadSavestate(bytes))
  local state=emu.getState();assert(state['cpu.k']==0x83 and state['cpu.pc']==0x9204)
  assert(u24(0x7e0092)==0xcb3da7)
  p('SAME_ROM_CHECKPOINT key='..key..' first='..first..' last='..last..'; controller input only, no data/PC/VM writes')
 end
end,emu.callbackType.exec,0x80f540,0x80f550,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if loaded then p(string.format('X_NATIVE_SKIP relative=%d held=%04X',n-loadAt,u(0x7e03ec)))end
end,emu.callbackType.exec,0xfb78d6,0xfb78d6,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if loaded and not returned and u24(0x7e0092)==0xcb273b then
  returned=true;due=n+60
  dump('returned.ram',emu.memType.snesWorkRam,0x20000)
  p('RETURNED_TO_MAP relative='..(n-loadAt))
 end
end,emu.callbackType.exec,0x80f5b0,0x80f5b0,emu.cpuType.snes,m)
emu.addEventCallback(function()
 local input={a=false,b=false,x=false,y=false,start=false,select=false,l=false,r=false,up=false,down=false,left=false,right=false}
 local t=n-loadAt
 if loaded and t>=first and t<last then input[key]=true end
 if loaded and acknowledge and emu.read(0x7e00aa,m)==6 and n%30<3 then input.a=true end
 -- Exercise ordinary map control after the battle has returned.
 if due and n>=due+20 and n<due+21 then input.right=true end
 if due and n>=due+40 and n<due+48 then input.a=true end
 if due and n>=due+100 and n<due+108 then if save then input.up=true else input.b=true end end
 if save and due and ((n>=due+150 and n<due+158) or (n>=due+260 and n<due+268) or (n>=due+400 and n<due+408)) then input.a=true end
 emu.setInput(input,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 n=n+1
 if due and n==due then shot('map')end
 if due and n==due+80 then shot('map-control')end
 if save and due and n==due+220 then shot('save-menu')end
 if save and due and n==due+350 then shot('save-confirm')end
 if due and n==due+(save and 520 or 150) then
  shot('final');dump('end.srm',emu.memType.snesSaveRam,8192)
  p(string.format('DONE script=%06X selected=%d cursor=%04X/%04X',u24(0x7e0092),u(0x7e0ea4),u(0x7e0e84),u(0x7e0e86)))
  file:close();emu.stop(0)
 end
 if n>=4000 then assert(returned,'battle did not return');error('post-battle controller check did not finish')end
end,emu.eventType.endFrame)
