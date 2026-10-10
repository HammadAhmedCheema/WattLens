"""Record real OpenRouter model outputs on consented synthetic/redacted samples."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import ROOT, settings
from app.extraction import preprocess, extract
from app.brief import generate
from app.engine import audit

async def run(args):
    for kind in ['appliance','bill']:
        path=Path(args.label if kind=='appliance' else args.bill)
        _,clean=preprocess(path.read_bytes(),path.name)
        start=time.monotonic();result=await extract(clean,kind,demo=False)
        if result['error']: raise RuntimeError(result['error'] + ' Existing demo fixture was not overwritten.')
        record={'provenance':'real_model_on_user_supplied_sample','model_name':settings.model_name,
                'recorded_at':datetime.now(timezone.utc).isoformat(),'seconds':round(time.monotonic()-start,2),
                'output':result['fields']}
        (ROOT/'demo'/f'{kind}.json').write_text(json.dumps(record,indent=2))
        print(f'{kind}: recorded in {record["seconds"]} seconds')
    household=json.loads((ROOT/'demo'/'household.json').read_text())
    output= audit(household['appliances'],household['bill'])
    brief,source,error=await generate(output)
    if source!='live_model': raise RuntimeError(f'Brief was not a live valid model result: {error}. Existing brief preserved.')
    (ROOT/'demo'/'brief.json').write_text(json.dumps({'provenance':'real_model_on_synthetic_household',
        'model_name':settings.model_name,'recorded_at':datetime.now(timezone.utc).isoformat(),'output':brief},indent=2))
    print('Brief: recorded; numeric allow-list passed.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label',default=str(ROOT/'samples'/'label.png'))
    p.add_argument('--bill',default=str(ROOT/'samples'/'bill.png'))
    asyncio.run(run(p.parse_args()))
