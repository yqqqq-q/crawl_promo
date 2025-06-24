import tldextract

def normalize_domain(url):
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}" 

if __name__ == '__main__':
    print(normalize_domain("us.shein.com"))