import matplotlib.pyplot as plt
import numpy as np

def is_prime(num):
    if num <= 1:
        return False
    if num <= 3:
        return True
    if num % 2 == 0 or num % 3 == 0:
        return False
    i = 5
    while i * i <= num:
        if num % i == 0 or num % (i + 2) == 0:
            return False
        i += 6
    return True

def plot_factor_circle(nmax, num_layers):
    angles = np.linspace(0, 2 * np.pi, num=nmax, endpoint=False)
    x = np.sin(angles)
    y = np.cos(angles)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim([-1.2, 1.2])
    ax.set_ylim([-1.2, 1.2])

    for layer in range(1, num_layers + 1):
        for i in range(nmax * (layer - 1), nmax * layer):
            angle = (i % nmax) * (2 * np.pi / (nmax))
            radius = 0.5 + (0.1 * layer)
            text_x = radius * np.sin(angle)
            text_y = radius * np.cos(angle)
            if is_prime(i + 1):
                ax.text(text_x, text_y,
                        str(i + 1),
                        color='white',
                        backgroundcolor='black',
                        fontsize=6,
                        ha='center',
                        va='center',
                        rotation=angle / np.pi)
            else:
                ax.text(text_x,text_y,
                        str(i + 1),
                        color='black',
                        fontsize=6,
                        ha='center',
                        va='center',
                        rotation=angle / np.pi)
                
    
    ax.set_aspect('equal', adjustable='datalim')
    ax.axis('off')
    fig.canvas.manager.set_window_title(f"nmax={nmax}, num_layers={num_layers}")
    plt.tight_layout()
    plt.show()  
    

factor = int(input("nmax: "))
layer = int(input("num_layers: "))

plot_factor_circle(factor, layer)
