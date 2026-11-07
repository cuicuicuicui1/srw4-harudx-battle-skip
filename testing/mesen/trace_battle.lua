local out=assert(os.getenv('PROBE_OUT'))
local f=assert(io.open(assert(os.getenv('PROBE_ROUTE')),'r'));local route=assert(load('return '..f:read('*a')))();f:close()
local n=0;local m=emu.memType.snesMemory;local log=assert(io.open(out..'/trace.log','w'))
local function p(s)log:write(s..'\n');log:flush()end
local function u(a)return emu.read(a,m)|(emu.read(a+1,m)<<8)end
local function u24(a)return u(a)|(emu.read(a+2,m)<<16)end
local function cpu()local s=emu.getState();return string.format('pc=%02X:%04X A=%04X X=%04X Y=%04X PS=%02X S=%04X D=%04X DBR=%02X',s['cpu.k'],s['cpu.pc'],s['cpu.a'],s['cpu.x'],s['cpu.y'],s['cpu.ps'],s['cpu.sp'],s['cpu.d'],s['cpu.dbr'])end
local function dump(name,kind,base,size)local t={};for a=0,size-1 do t[#t+1]=string.char(emu.read(base+a,kind)&255)end;local f=assert(io.open(out..'/'..name,'wb'));f:write(table.concat(t));f:close()end
local function state(label)p(string.format('%s frame=%d selected=%d cursor=%04X/%04X attacker=%d defender=%d weapon=%d/%d animkey=%04X script=%06X cb=%06X %s',label,n,u(0x7e0ea4),u(0x7e0e84),u(0x7e0e86),u(0x7e0ea6),u(0x7e0ea8),u(0x7e0eac),u(0x7e0eae),u(0x7e0f17),u24(0x7e0092),u24(0x7e00cb),cpu()))end
local s=assert(io.open(assert(os.getenv('PROBE_SRAM')),'rb'));local b=s:read('*a');s:close();assert(#b==8192);for i=1,#b do emu.write(i-1,b:byte(i),emu.memType.snesSaveRam)end
local lastScript=nil;local capturedStart=false
local gate=false;local gateHits=0;local returned=false
emu.addMemoryCallback(function()
 if u24(0x7e0092)==0xcb3da7 then
  gateHits=gateHits+1
  p(string.format('SKIP_GATE frame=%d phase=%02X held=%04X pressed=%04X %s',n,emu.read(0x7e00ab,m),u(0x7e03ec),u(0x7e03f0),cpu()))
  if not gate then
   gate=true;dump('gate.ram',emu.memType.snesWorkRam,0,0x20000)
   local f=assert(io.open(out..'/before-x-window.mss','wb'));f:write(emu.createSavestate());f:close()
  end
 end
end,emu.callbackType.exec,0x839204,0x839204,emu.cpuType.snes,m)
emu.addMemoryCallback(function()p('X_NATIVE_SKIP frame='..n..' '..cpu())end,emu.callbackType.exec,0xfb78d6,0xfb78d6,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 local script=u24(0x7e0092)
 if gate and not returned and script==0xcb273b then
  returned=true;dump('returned.ram',emu.memType.snesWorkRam,0,0x20000)
  p('RETURNED_TO_MAP frame='..n..' '..cpu())
 end
 if n>=6850 and n<7150 and script~=lastScript then
  lastScript=script;p(string.format('START_VM frame=%d script=%06X opcode=%02X BF=%04X buttons=%04X/%04X/%04X opts=%04X %s',n,script,emu.read(script,m),u(0x7e00bf),u(0x7e03e8),u(0x7e03ea),u(0x7e03f0),u(0x7e1002),cpu()))
 end
 if script==0xcb3e00 and not capturedStart then capturedStart=true end
end,emu.callbackType.exec,0x80f5b0,0x80f5b0,emu.cpuType.snes,m)
emu.addMemoryCallback(function(addr,val)if n>6500 and n<8000 then p(string.format('BF_WRITE frame=%d addr=%06X val=%02X %s',n,addr,val,cpu()))end end,emu.callbackType.write,0xbf,0xc0,emu.cpuType.snes,emu.memType.snesWorkRam)
local resets=0;local reset=tonumber(os.getenv('PROBE_RESET'));emu.addMemoryCallback(function()resets=resets+1;p('RESET frame='..n..' '..cpu())end,emu.callbackType.exec,reset,reset,emu.cpuType.snes,m)
local seen={};local hits=0
for _,at in ipairs({0x81951c,0x81954b,0x8195c6,0x8195e4,0x8194dc,0x81972a,0xc1951c,0xc1954b,0xc195c6,0xc195e4,0xc194dc,0xc1972a}) do
 emu.addMemoryCallback(function()
  if n>3500 and hits<400 then hits=hits+1;p(string.format('NAME_CONSUMER pc=%06X frame=%d cb=%06X source17E7=%04X nest=%02X parent=%06X %s',at,n,u24(0x7e00cb),u(0x7e17e7),emu.read(0x7e0e26,m),u24(0x7e0e17),cpu())) end
 end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)
end
emu.addMemoryCallback(function()
 local cb=u24(0x7e00cb)
 if n>3500 and (cb>=0xf26cc3 and cb<0xf26cd6 or cb>=0xf2ffe0 or cb>=0xd2ffe0 and cb<0xd30000) and not seen[cb] then seen[cb]=true;p(string.format('NAME_READ frame=%d cb=%06X byte=%02X nest=%d parent=%06X %s',n,cb,emu.read(cb,m),emu.read(0x7e0e26,m),u24(0x7e0e17),cpu())) end
end,emu.callbackType.exec,0x819776,0x819776,emu.cpuType.snes,m)
for _,at in ipairs({0x83dffd,0x83e01c,0x819369,0xc19369}) do emu.addMemoryCallback(function()
 if n>7000 and n<8200 then p(string.format('QUOTE_ROOT pc=%06X frame=%d cb=%06X p20=%06X sourceA=%04X sourceD=%04X %s',at,n,u24(0x7e00cb),u24(0x7e0020),u(0x7e17e5+u(0x7e0ea6)),u(0x7e17e5+u(0x7e0ea8)),cpu())) end
end,emu.callbackType.exec,at,at,emu.cpuType.snes,m) end
for _,at in ipairs({0x83d364,0x83d3ab,0x80c450,0x80c4c0})do emu.addMemoryCallback(function()
 if n>6000 then p(string.format('OUTCOME pc=%06X frame=%d F31=%04X F32=%04X F33=%04X F34=%04X pilotD=%04X p20=%06X %s',at,n,u(0x7e0f31),u(0x7e0f32),u(0x7e0f33),u(0x7e0f34),u(0x7e17e5+u(0x7e0ea8)),u24(0x7e0020),cpu()))end
end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)end
local cutCheckpoint=false
for _,at in ipairs({0x83f1b1,0x83f228,0x83f254,0x83eedd,0x83eee0,0xc3f1b1,0xc3f228,0xc3f254,0xc3eedd,0xc3eee0})do emu.addMemoryCallback(function()
 if n>5000 then
  p(string.format('CUT_NATIVE pc=%06X frame=%d skill=%04X flags=%04X weapon=%04X unit=%04X pilot=%04X %s',at,n,u(0x7e0022),u(0x7e0028),u(0x7e0eac),u(0x7e1865+u(0x7e0ea8)),u(0x7e17e5+u(0x7e0ea8)),cpu()))
  if (at==0x83f228 or at==0xc3f228) and not cutCheckpoint then
   cutCheckpoint=true;local f=assert(io.open(out..'/before-cut-rng.mss','wb'));f:write(emu.createSavestate());f:close()
   p('CUT_RNG_CHECKPOINT skill='..u(0x7e0022))
  end
 end
end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)end
local captured=false
for _,at in ipairs({0x819369,0xc19369}) do emu.addMemoryCallback(function()
 if os.getenv('CAPTURE_SELECTOR') and not captured and u24(0x7e00cb)==0xeb48f3 then
  captured=true;local f=assert(io.open(out..'/before-selector.mss','wb'));f:write(emu.createSavestate());f:close()
  dump('before-selector.ram',emu.memType.snesWorkRam,0,0x20000);p('SAME_ROM_SELECTOR_CHECKPOINT '..cpu())
 end
end,emu.callbackType.exec,at,at,emu.cpuType.snes,m) end
local active=nil;local count=0
emu.addMemoryCallback(function()
 active={source=u24(0x7e0010),dest=u24(0x7e0013),frame=n};count=0;p(string.format('DECOMP_ENTRY frame=%d source=%06X dest=%06X return=%06X %s',n,active.source,active.dest,u24(0x7e0000+(emu.getState()['cpu.sp']+1)),cpu()))
end,emu.callbackType.exec,0x80f93d,0x80f93d,emu.cpuType.snes,m)
for _,at in ipairs({0x80f98d,0x80f9a8})do
 emu.addMemoryCallback(function()
  if not active then return end;count=count+1
  local limit=active.source==0xd20000 and 16384 or (active.source==0xfd0000 and 8192 or nil)
  if limit and count==limit+1 then p(string.format('FIRST_OUTPUT_OVER_EXPECTED frame=%d source=%06X dest=%06X count=%d %s',n,active.source,active.dest,count,cpu()));dump('first-overrun.ram',emu.memType.snesWorkRam,0,0x20000)end
 end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)
end
emu.addMemoryCallback(function()if active then local st=emu.getState();p(string.format('DECOMP_EXIT frame=%d source=%06X dest=%06X count=%d Y=%04X X=%04X',n,active.source,active.dest,count,st['cpu.y'],st['cpu.x']));active=nil end end,emu.callbackType.exec,0x80f9dc,0x80f9dc,emu.cpuType.snes,m)
for _,at in ipairs({0x83d0e0,0x83d10e,0x83d6c8,0x83d3ab,0x83dffd,0x82818e,0x82ca1e})do emu.addMemoryCallback(function()state(string.format('ANIM_CONSUMER_%06X',at))end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)end
if os.getenv('TRACE_QUOTE') then
 local calls=0
 for _,at in ipairs({0x8194dc,0x81977b,0xc194dc,0xc1977b})do emu.addMemoryCallback(function()
  if n>6900 and n<9700 and calls<800 then calls=calls+1;p(string.format('QUOTE pc=%06X frame=%d cb=%06X byte=%02X nest=%d layout=%04X gate=%04X %s',at,n,u24(0x7e00cb),emu.read(u24(0x7e00cb),m),emu.read(0x7e0e26,m),u(0x7e0e2c),u(0x7e0e7e),cpu()))end
 end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)end
 emu.addMemoryCallback(function(addr,value)if n>6900 and n<9700 then p(string.format('QUOTE_GATE_WRITE frame=%d addr=%06X value=%02X %s',n,addr,value,cpu()))end end,emu.callbackType.write,0x7e0e7e,0x7e0e7f,emu.cpuType.snes,m)
end
if os.getenv('TRACE_GATE') then
 local calls=0
 emu.addMemoryCallback(function(addr,value)if n>7050 and n<8100 then p(string.format('GATE_PHYSICAL_WRITE frame=%d addr=%06X value=%02X %s',n,addr,value,cpu()))end end,emu.callbackType.write,0xe7e,0xe7f,emu.cpuType.snes,emu.memType.snesWorkRam)
 for _,at in ipairs({0x81a483,0x81a48d,0x82c505,0x82feff,0x819a5b,0x83d364})do emu.addMemoryCallback(function()
  if n>7050 and n<8100 and calls<200 then calls=calls+1;p(string.format('GATE_CONSUMER pc=%06X frame=%d motion=%06X gate=%04X quoteVM=%02X/%02X layout=%04X %s',at,n,u24(0x7e0050),u(0x7e0e7e),emu.read(0x7e00aa,m),emu.read(0x7e00ab,m),u(0x7e0e2c),cpu()))end
 end,emu.callbackType.exec,at,at,emu.cpuType.snes,m)end
end
if os.getenv('TRACE_MENU') then
 local pending=nil;local calls=0
 emu.addMemoryCallback(function()
  if n>=7260 and n<=7340 and calls<1600 then
   calls=calls+1;pending={frame=n,ptr=u24(0x7e001a)}
   p(string.format('MENU_ENTER frame=%d ptr=%06X gate=%04X script=%06X stack=%06X/%06X %s',n,pending.ptr,u(0x7e0e7e),u24(0x7e0092),u24(0x7e0000+emu.getState()['cpu.sp']+1),u24(0x7e0000+emu.getState()['cpu.sp']+4),cpu()))
  end
 end,emu.callbackType.exec,0x818a78,0x818a78,emu.cpuType.snes,m)
 emu.addMemoryCallback(function()
  if pending then p(string.format('MENU_RETURN frame=%d fromFrame=%d ptr=%06X from=%06X gate=%04X %s',n,pending.frame,u24(0x7e001a),pending.ptr,u(0x7e0e7e),cpu()));pending=nil end
 end,emu.callbackType.exec,0x818a7d,0x818a7d,emu.cpuType.snes,m)
end
emu.addEventCallback(function()
 local key={a=false,b=false,start=false,up=false,down=false,left=false,right=false,l=false,r=false,x=false,y=false}
 for _,e in ipairs(route.events)do if n>=e[1]and n<e[2]then key[e[3]]=true end end;emu.setInput(key,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 n=n+1
 if n==3500 and #route.writes>0 then
  for _,w in ipairs(route.writes)do for i=1,#w.bytes do emu.write(0x7e0000+w.address+i-1,w.bytes[i],m)end end;p('CONTROLLED_FIXTURE native map consistency unit/XY/occupancy/EN/HP only, no PC/event/result writes');state('FIXTURE')
 end
 if n%1000==0 then state('TICK')end
 if route.shots[n]then local f=assert(io.open(out..'/frame-'..n..'.png','wb'));f:write(emu.takeScreenshot());f:close();dump('frame-'..n..'.ram',emu.memType.snesWorkRam,0,0x20000);state('SHOT')end
 if n>=route.frames then dump('end.srm',emu.memType.snesSaveRam,0,8192);p('DONE frames='..n..' resets='..resets);log:close();emu.stop(0)end
end,emu.eventType.endFrame)
