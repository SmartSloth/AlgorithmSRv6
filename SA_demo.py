def demo_func(x):
    x1, x2, x3 = x
    return x1 ** 2 + (x2 - 0.05) ** 2 + x3 ** 2

# %% Do SA
from sko.SA import SA

sa = SA(func=demo_func, x0=[1, 1, 1])
x_star, y_star = sa.run()
print(x_star, y_star)

# sa = SA(func=demo_func,
#         x0=[1, 1, 1],
#         T_max=1,
#         T_min=1e-9,
#         L=300,
#         max_stay_counter=150)
# best_x, best_y = sa.run()
# print('best_x:', best_x, 'best_y', best_y)

# %% Plot the result
import matplotlib.pyplot as plt
import pandas as pd

plt.plot(pd.DataFrame(sa.best_y_history).cummin(axis=0))
plt.savefig("SA.png")
plt.show()

# %%
from sko.SA import SAFast

sa_fast = SAFast(func=demo_func,
                 x0=[1, 1, 1],
                 T_max=1,
                 T_min=1e-9,
                 q=0.99,
                 L=300,
                 max_stay_counter=150)
sa_fast.run()
print('Fast Simulated Annealing: best_x is ', sa_fast.best_x, 'best_y is ',
      sa_fast.best_y)

# %%
from sko.SA import SABoltzmann

sa_boltzmann = SABoltzmann(func=demo_func,
                           x0=[1, 1, 1],
                           T_max=1,
                           T_min=1e-9,
                           q=0.99,
                           L=300,
                           max_stay_counter=150)
sa_boltzmann.run()
print('Boltzmann Simulated Annealing: best_x is ', sa_boltzmann.best_x,
      'best_y is ', sa_fast.best_y)

# %%
from sko.SA import SACauchy

sa_cauchy = SACauchy(func=demo_func,
                     x0=[1, 1, 1],
                     T_max=1,
                     T_min=1e-9,
                     q=0.99,
                     L=300,
                     max_stay_counter=150)
sa_cauchy.run()
print('Cauchy Simulated Annealing: best_x is ', sa_cauchy.best_x, 'best_y is ',
      sa_cauchy.best_y)
