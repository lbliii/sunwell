# Quick Start Guide for Sunwell

Welcome to the Sunwell Quick Start Guide! This guide will help you set up and start using Sunwell effectively. We'll cover the essentials to get you up and running quickly.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- Python 3.8 or later
- Git

## Step 1: Clone the Repository

Start by cloning the Sunwell repository to your local machine. Run the following command:

```bash
git clone https://github.com/yourusername/sunwell.git
cd sunwell
```

## Step 2: Set Up the Environment

It's recommended to use a virtual environment to manage dependencies. Set it up with:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

Then, install the required packages:

```bash
pip install -r requirements.txt
```

## Step 3: Initialize Sunwell

Sunwell needs to be initialized before use. This involves setting up the `ExpertiseRetriever`. Here's how you can do it:

```python
from sunwell.models.protocol import ExpertiseRetriever
from sunwell.models.embedding import HashEmbedding
from sunwell.schema.lens import Lens

# Initialize lens and embedder
sample_lens = Lens()  # Replace with actual lens configuration
embedder = HashEmbedding()

# Create and initialize retriever
retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder)
await retriever.initialize()

# Check if initialization was successful
stats = retriever.get_stats()
assert stats["initialized"], "Initialization failed"
```

**Note**: Ensure that your lens and embedder are correctly configured.

## Step 4: Save and Load Episodes

Sunwell allows you to save episodes to a JSON file. Use the following code to save your episodes:

```python
from pathlib import Path
from sunwell.runtime.episode import Episode

# Assuming `episodes` is a list of Episode objects
episode_runtime = Episode(episodes=your_episodes_list)
episode_runtime.save(Path("path/to/save.json"))
```

## Step 5: Stream Data

You can stream data using the `generate_stream` method. Here's an example:

```python
from sunwell.models.protocol import Protocol

protocol_instance = Protocol()  # Ensure Protocol is correctly instantiated

async for response in protocol_instance.generate_stream("Your prompt here"):
    print(response)
```

## Troubleshooting

- **Initialization Error**: Ensure that your lens and embedder are correctly configured. Verify the integrity of your data sources.
- **Dependency Issues**: Double-check that all dependencies in `requirements.txt` are installed in your virtual environment.

## Next Steps

- Explore the [full documentation](https://github.com/yourusername/sunwell/wiki) for in-depth guides and explanations.
- Experiment with different configurations and embeddings to optimize performance for your specific use case.

Congratulations! You've successfully set up and started using Sunwell. If you encounter any issues, feel free to consult the troubleshooting section or reach out to the community for support.