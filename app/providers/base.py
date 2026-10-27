import httpx

class ProviderError(Exception): pass


def get_json(client,url,**kwargs):
    try:
        response=client.get(url,**kwargs)
        if response.status_code==401 or response.status_code==403: raise ProviderError('Provider rejected credentials or plan access')
        if response.status_code==429: raise ProviderError('Provider quota reached; retry at the next refresh')
        if response.status_code!=200: raise ProviderError(f'Provider unavailable (HTTP {response.status_code})')
        return response.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise ProviderError('Provider request failed or returned invalid data') from None
