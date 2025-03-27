# rl_training.py
import numpy as np
import json

def predict_reward(features, weights):
    """Compute the predicted reward given features and weights."""
    return np.dot(features, weights)

def update_weights(weights, features, reward, predicted_reward, alpha=0.01):
    """Update weights using a gradient ascent step."""
    error = reward - predicted_reward
    return weights + alpha * error * features

def train_rl_model(num_examples=100, epochs=1000, alpha=0.01):
    """
    Train a simple RL model using simulated data.
    Features: [rating_norm, availability, price_factor, language_match, learning_style_match]
    """
    np.random.seed(42)
    # generate synthetic feature vectors for each example (values between 0 and 1)
    features_data = np.random.rand(num_examples, 5)
    # define a true underlying weight vector (for simulation purposes)
    true_weights = np.array([0.4, 0.3, 0.2, 0.1, 0.0])
    # generate rewards as a dot product plus some noise
    rewards = features_data.dot(true_weights) + np.random.randn(num_examples) * 0.05
    # initialize weight vector (our starting guess)
    weights = np.array([0.35, 0.25, 0.15, 0.15, 0.10])
    
    for epoch in range(epochs):
        for i in range(num_examples):
            f = features_data[i]
            r = rewards[i]
            pred = predict_reward(f, weights)
            weights = update_weights(weights, f, r, pred, alpha)
    
    return weights

def main():
    learned_weights = train_rl_model()
    weights_dict = {
        "rating_weight": float(learned_weights[0]),
        "availability_weight": float(learned_weights[1]),
        "price_weight": float(learned_weights[2]),
        "language_weight": float(learned_weights[3]),
        "learning_style_weight": float(learned_weights[4])
    }
    with open("weights.json", "w") as f:
        json.dump(weights_dict, f, indent=4)
    print("Learned weights saved to weights.json")

if __name__ == "__main__":
    main()
