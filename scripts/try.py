
import biobricks as bb
import pandas as pd

paths = bb.assets("compait")
df = pd.read_parquet(paths.compait_parquet)
print(df.head())

## Additional Information

Collaborative Modeling Project for Acute Inhalation Toxicity (CoMPAIT)


![alt text](image.png)