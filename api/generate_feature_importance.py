import pickle
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.family'] = 'DejaVu Sans'

with open('best_model_xgboost.pkl', 'rb') as f:
    model = pickle.load(f)

with open('features_list.txt') as f:
    features = [l.strip() for l in f.readlines()]

importances = model.feature_importances_
idx = np.argsort(importances)[::-1][:20]

fig, ax = plt.subplots(figsize=(10, 8))
ax.barh([features[i] for i in idx], importances[idx], color='#F4A460')
ax.set_xlabel('Importance (gain moyen par split)', fontsize=11)
ax.set_title('Top 20 Features les Plus Importantes - XGBoost (Option C)',
             fontsize=12, fontweight='bold')
ax.invert_yaxis()
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig('feature_importance_optionC.png', dpi=300, bbox_inches='tight')
print('Image sauvegardee : feature_importance_optionC.png')
