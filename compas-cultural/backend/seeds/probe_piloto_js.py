"""Find Piloto's Strapi API URL by inspecting JS bundles."""
import asyncio, httpx, json, re

async def probe():
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=30) as c:
        # Get the page html
        r = await c.get('https://bibliotecapiloto.gov.co/agenda/embed')
        html = r.text
        
        # Find all JS chunks
        js_files = re.findall(r'"(/_next/static/chunks/[^"]+\.js)"', html)
        js_files += re.findall(r'"(/_next/static/[^/]+/pages/agenda[^"]+)"', html)
        print(f"Found {len(js_files)} JS files")
        
        base = 'https://bibliotecapiloto.gov.co'
        
        # Search each chunk for API URLs
        found_api_urls = set()
        for js in js_files[:20]:  # Check first 20 chunks
            r2 = await c.get(base + js)
            chunk = r2.text
            # Look for API URL patterns
            apis = re.findall(r'(https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}/[^"\'` ]{3,})', chunk)
            for api in apis:
                if 'bibliotecapiloto' in api or 'bpp' in api or 'strapi' in api or '/api/' in api:
                    found_api_urls.add(api)
            
            # Look for env var patterns like process.env.NEXT_PUBLIC
            envs = re.findall(r'NEXT_PUBLIC_[A-Z_]+[^"\']*["\']([^"\']+)["\']', chunk)
            if envs:
                print(f"Env vars in {js}:", envs[:5])
        
        print("API URLs found:", found_api_urls)
        
        # Also try known CMS subdomains  
        for subdomain in ['cms', 'api', 'strapi', 'admin', 'content', 'backend']:
            url = f'https://{subdomain}.bibliotecapiloto.gov.co/api/activities?pagination[limit]=2'
            try:
                r3 = await c.get(url, timeout=8)
                if r3.status_code == 200:
                    print(f"HIT: {url} -> {r3.text[:300]}")
                else:
                    print(f"{url} -> {r3.status_code}")
            except Exception as e:
                print(f"{url} -> timeout/error")

asyncio.run(probe())
