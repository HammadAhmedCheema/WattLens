const $ = (s, root=document) => root.querySelector(s);
const toast = message => {$('#toast').textContent=message; setTimeout(()=>$('#toast').textContent='',12000)};
const presets = JSON.parse(document.querySelector('#category-defaults').textContent);
document.addEventListener('change',e=>{
 if(e.target.matches('.category-select')){const form=e.target.form,p=presets[e.target.value];form.hours_per_day.value=p.hours;form.load_factor.value=p.load_factor;$('.preset-note',form).textContent=`Category defaults: ${p.watts} W, ${p.hours} hours/day, factor ${p.load_factor}. These are editable starting guesses.`}
 if(e.target.id==='photos') $('#file-list').textContent=Array.from(e.target.files).map(f=>f.name).join(' · ');
});
document.addEventListener('dragover',e=>{const z=e.target.closest('.dropzone');if(z){e.preventDefault();z.classList.add('dragover')}});
document.addEventListener('dragleave',e=>e.target.closest('.dropzone')?.classList.remove('dragover'));
document.addEventListener('drop',e=>{const z=e.target.closest('.dropzone');if(z){e.preventDefault();z.classList.remove('dragover');const input=$('input[type=file]',z);input.files=e.dataTransfer.files;input.dispatchEvent(new Event('change',{bubbles:true}))}});
document.addEventListener('submit',async e=>{
 const form=e.target;if(form.id!=='upload-form')return;e.preventDefault();const input=$('input[type=file]',form),files=Array.from(input.files);
 if(!files.length)return;if(files.length>12)return toast('Choose at most twelve photos.');if(files.some(f=>f.size>10*1024*1024))return toast('Each image must be no larger than 10 MB.');
 const button=$('button[type=submit], button',form),progress=$('.upload-progress',form);button.disabled=true;progress.hidden=false;
 let firstDoc=null,sections=[];
 try{for(let i=0;i<files.length;i++){
  progress.textContent=`Reading photo ${i+1} of ${files.length} with OpenRouter… Transcribing, then extracting fields.`;
  const body=new FormData();body.append(input.name,files[i]);const response=await fetch(form.action,{method:'POST',body});
  if(!response.ok){const problem=await response.json();throw Error(typeof problem.detail==='string'?problem.detail:'Unable to read the upload.')}
  const doc=new DOMParser().parseFromString(await response.text(),'text/html');if(!firstDoc)firstDoc=doc;
  if(form.action.endsWith('/appliances/extract')){const section=$('.review-grid',doc);section.id=`draft-${i+1}`;$('form',section).setAttribute('hx-target',`#draft-${i+1}`);sections.push(section)}
 }
 const main=$('main');main.replaceChildren(...Array.from($('main',firstDoc).childNodes));if(sections.length){main.querySelectorAll('.review-grid').forEach(n=>n.remove());sections.forEach(s=>main.appendChild(s))}
 window.htmx?.process(main);window.scrollTo({top:0});document.title='Review extracted details · WattLens';
 }catch(error){toast(error.message);button.disabled=false;progress.hidden=true}
});
document.addEventListener('htmx:responseError',e=>{try{const data=JSON.parse(e.detail.xhr.responseText);toast(typeof data.detail==='string'?data.detail:'Check the form values and try again.')}catch{toast('Request failed. Please try again.')}});
document.addEventListener('htmx:sendError',()=>toast('The local app is unreachable. Please check the server.'));
document.addEventListener('DOMContentLoaded',()=>{
 const dataNode=$('#chart-data');if(!dataNode||!window.Chart)return;const data=JSON.parse(dataNode.textContent),rows=data.appliances;
 const palette=['#366347','#75905a','#9ead7b','#bdc49a','#d3ceaa','#acbba5','#8d9f87'];
 const whiskers={id:'rangeWhiskers',afterDatasetsDraw(chart){const {ctx,scales:{x,y}}=chart;ctx.save();ctx.strokeStyle='#658054';ctx.lineWidth=1.5;rows.forEach((r,i)=>{const yy=y.getPixelForValue(i),lo=x.getPixelForValue(r.low_kwh),hi=x.getPixelForValue(r.high_kwh);ctx.beginPath();ctx.moveTo(lo,yy);ctx.lineTo(hi,yy);ctx.moveTo(lo,yy-5);ctx.lineTo(lo,yy+5);ctx.moveTo(hi,yy-5);ctx.lineTo(hi,yy+5);ctx.stroke()});ctx.restore()}};
 new Chart($('#ranked-chart'),{type:'bar',data:{labels:rows.map(r=>r.name),datasets:[{label:'Estimated kWh / month',data:rows.map(r=>r.monthly_kwh),backgroundColor:rows.map((_,i)=>palette[i%palette.length]),borderRadius:4,barThickness:20}]},options:{indexAxis:'y',maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,suggestedMax:Math.max(...rows.map(r=>r.high_kwh))*1.05,title:{display:true,text:'Estimated kWh / month'},grid:{color:'#edf0e8'}},y:{title:{display:true,text:'Appliance'},grid:{display:false}}}},plugins:[whiskers]});
 new Chart($('#share-chart'),{type:'doughnut',data:{labels:rows.map(r=>r.name),datasets:[{data:rows.map(r=>r.monthly_kwh),backgroundColor:rows.map((_,i)=>palette[i%palette.length]),borderWidth:3,borderColor:'#fff'}]},options:{maintainAspectRatio:false,cutout:'68%',plugins:{legend:{position:'bottom',labels:{boxWidth:8,boxHeight:8,font:{size:10},padding:12}},tooltip:{callbacks:{label:c=>`${c.label}: ${rows[c.dataIndex].share_percent}% of estimate`}}}}});
});
