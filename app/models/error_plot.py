import numpy as np
import matplotlib.pyplot as plt
from sklearn.neighbors import KernelDensity

class ErrorPlotter:
    def __init__(self):
        pass
    
    
    def plot_error(self, error, kde, rel_error=False, name=None):
        fig, ax = plt.subplots(figsize=(12, 8))
        error = np.atleast_2d(error).T  # Reshape error to 2D if it's 1D
        
        if rel_error:
            X_plot = np.linspace(min(-5, np.min(error) - 2), max(5, np.max(error) + 2), 1000)[:, np.newaxis]
        else:
            X_plot = np.linspace(min(np.min(error), -np.max(error)), max(-np.min(error), np.max(error)), 1000)[:, np.newaxis]

        log_dens = np.exp(kde.score_samples(X_plot))
        ax.plot(X_plot[:, 0], log_dens, linestyle="-")
        
        # Plot the original values of error
        ax.plot(error[:, 0], -0.005 - 0.01 * np.random.random(error.shape[0]), "+k")
        
        # Add labels to the axes
        ax.set_xlabel('Log-relative Selectivity Error' if rel_error else 'Error', fontsize=35)
        ax.set_ylabel('Probability Density', fontsize=40)
        ax.tick_params(axis='both', which='major', labelsize=30)
        
        plt.tight_layout()
        plot_path = f'{name}.png' if name else 'dynamic_error_plot.png'
        prefix = './app/static/'
        total = prefix + plot_path
        fig.savefig(total, dpi=800)
        plt.close(fig)  # Close the plot to free up memory
        return plot_path


    def process_and_plot(self, error_data, name="dynamic_error_plot", rel_error=False):
        error = np.array(error_data)
        
        # Fit Kernel Density Estimation
        kde = KernelDensity(kernel='gaussian', bandwidth=0.5).fit(error[:, None])
        return self.plot_error(error, kde, rel_error, name)
    
    
    def calculate_density(self, error_data):
        error = np.array(error_data)
        
        # MARK: hardcode
        np.random.seed(42)
        error = np.random.normal(0, 1, 400)
        
        kde = KernelDensity(kernel='gaussian', bandwidth=0.5).fit(error[:, None])
        
        # Define x min and x max values
        x_min = error.min() - 1
        x_max = error.max() + 1
        x_range = np.linspace(x_min, x_max, num=int((x_max - x_min) / 0.0001))

        # Calculate y values
        log_dens = kde.score_samples(x_range[:, None])
        y_values = np.exp(log_dens)  # Convert log density to normal density

        # Store values
        density_curve = list(zip(x_range.tolist(), y_values.tolist()))
        print(density_curve)

        return density_curve