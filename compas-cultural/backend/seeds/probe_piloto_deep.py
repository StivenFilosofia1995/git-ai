"""Probe Piloto backend for real event API."""
import asyncio, httpx, json, re

async def probe():
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=20) as c:
        r = await c.get('https://bibliotecapiloto.gov.co/_next/data/tpUeX9x8kgHPcRBh04h9p/agenda.json')
        d = r.json()
        text = json.dumps(d, ensure_ascii=False)
        
        urls = re.findall(r'https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}', text)
        unique_domains = set(urls)
        print('Domains in data:', unique_domains)
        
        keys_with_events = re.findall(r'"([\w]+)":\s*\[', text)
        print('Array keys:', list(set(keys_with_events)))
        
        print('Full text length:', len(text))
        # Save for inspection
        with open('seeds/piloto_agenda_data.json', 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print('Saved to seeds/piloto_agenda_data.json')
        
        # Also look for the JS env
        r2 = await c.get('https://bibliotecapiloto.gov.co/')
        env_urls = re.findall(r'(https?://[a-zA-Z0-9\-\.]+\.(gov\.co|com\.co|com))', r2.text)
        print('Frontend env URLs:', set(u[0] for u in env_urls))
        
        # check _next/static chunks for API url
        js_urls = re.findall(r'/_next/static/chunks/[^\s"\']+\.js', r2.text)
        if js_urls:
            print('Checking JS chunk for API URL:', js_urls[0])
            r3 = await c.get('https://bibliotecapiloto.gov.co' + js_urls[0])
            api_urls = re.findall(r'(https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}/[a-zA-Z/]*api[a-zA-Z/]*)', r3.text)
            print('API URLs in JS:', list(set(api_urls))[:10])

asyncio.run(probe())
