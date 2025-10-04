def smooth_series(vals, k=3):
    if len(vals) < k: return vals
    out = []
    for i in range(len(vals)):
        s = vals[max(0,i-k+1):i+1]
        out.append(sum(s)/len(s))
    return out
