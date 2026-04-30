"""Probe APIs for Piloto and EPM to discover JSON endpoints."""
import asyncio, httpx, json, re

async def probe():
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=20) as c:
        # ── Piloto: Next.js app ──────────────────────────────────────────
        print("=== PILOTO ===")
        r = await c.get("https://bibliotecapiloto.gov.co/")
        build_id = re.search(r'/_next/static/([^/]+)/_buildManifest', r.text)
        if build_id:
            bid = build_id.group(1)
            print("Build ID:", bid)
            for path in ["agenda", "agenda/embed"]:
                url = f"https://bibliotecapiloto.gov.co/_next/data/{bid}/{path}.json"
                r2 = await c.get(url)
                print(url, "->", r2.status_code, r2.text[:500])
        else:
            print("No Next.js build ID found.")
            scripts = re.findall(r'src=["\']?(/_next/static/[^"\'>\s]+)', r.text)
            print("Scripts:", scripts[:5])
        
        # Try straightly the GraphQL or REST patterns
        for url in [
            "https://bibliotecapiloto.gov.co/graphql",
            "https://bibliotecapiloto.gov.co/wp-json/",
            "https://bibliotecapiloto.gov.co/api/graphql",
        ]:
            r2 = await c.get(url)
            print(url, "->", r2.status_code, r2.text[:200])

        # ── EPM: AEM ────────────────────────────────────────────────────
        print("\n=== EPM ===")
        r = await c.get("https://www.grupo-epm.com/site/fundacionepm/programacion/")
        # Check inline data-layer JSON
        data_layers = re.findall(r'data-cmp-data-layer=[\'"]({[^\'">]+})', r.text)
        print(f"Found {len(data_layers)} data-cmp-data-layer attributes")
        for dl in data_layers[:5]:
            print(" ", dl[:200])
        
        # AEM content finder / Sling selectors
        for url in [
            "https://www.grupo-epm.com/site/fundacionepm/programacion.infinity.json",
            "https://www.grupo-epm.com/site/fundacionepm/programacion.1.json",
            "https://www.grupo-epm.com/content/epm/fundacionepm/es/programacion.model.json",
        ]:
            r2 = await c.get(url)
            print(url, "->", r2.status_code, r2.text[:300])

asyncio.run(probe())
