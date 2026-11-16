import re
def syllables(w):
    w=w.lower(); w=re.sub(r'[^a-z]','',w)
    if not w: return 0
    if len(w)<=3: return 1
    w=re.sub(r'(?:[^laeiouy]es|ed|[^laeiouy]e)$','',w); w=re.sub(r'^y','',w)
    return max(1,len(re.findall(r'[aeiouy]{1,2}',w)))
def fk_grade(text):
    words=re.findall(r"[A-Za-z][A-Za-z'\-]*",text)
    sents=max(1,len(re.findall(r'[.!?]+(?=\s|$|["”’])',text)))
    syl=sum(syllables(w) for w in words)
    return round(0.39*len(words)/sents+11.8*syl/len(words)-15.59,1)
