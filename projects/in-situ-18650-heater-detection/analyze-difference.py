#!/usr/bin/env python3

import pandas as pd
import numpy as np
import sys

columns = [ "time","target_temp[degC]","temp[degC]","pwm[%]","U1[degC]","U2[degC]","U3[degC]","U4[degC]","U5[degC]" ]
data = pd.read_csv(sys.argv[1], usecols=columns)
data['min_temp'] = data[['U1[degC]', 'U2[degC]', 'U3[degC]', 'U4[degC]', 'U5[degC]']].min(axis=1)
data['max_temp'] = data[['U1[degC]', 'U2[degC]', 'U3[degC]', 'U4[degC]', 'U5[degC]']].max(axis=1)
data['deltaT'] = abs(data['max_temp'] - data['min_temp'])

print("Data:")
print(data)

print("Observed temperature difference (deltaT):")
print(data['deltaT'].describe())

