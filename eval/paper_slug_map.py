"""Map paper claim titles to their query-side slug ids.

Each entry's KEY is the exact title used in PAPER_CLAIMS in build_corpus.py.
The VALUE is the slug id used in PAPER_QUERIES.

Why a separate file: titles get edited over time, slugs in queries are
deliberately short and stable. Decoupling them makes it possible to rename
titles without breaking queries.
"""
from __future__ import annotations

# title -> slug id (None = claim exists but no query references it)
TITLE_TO_SLUG: dict[str, str | None] = {
    # Transformer
    "Transformer: scaled dot-product attention definition": "tx-scaled-dot-product",
    "Transformer: multi-head attention lets the model attend to different representation subspaces": "tx-multi-head",
    "Transformer: positional encoding uses sinusoids": "tx-positional",
    "Transformer: training took 12 hours on 8 P100 GPUs for the base model": "tx-training-compute",
    "Transformer: BLEU gains on WMT 2014 EN-DE were +2.0 over the prior SOTA": "tx-bleu-results",
    # BERT
    "BERT: bidirectional pretraining via masked language modeling": "bert-mlm",
    "BERT: next sentence prediction (NSP) was later shown to be mostly useless": "bert-nsp",
    "BERT: 110M parameters for BERT-base, 340M for BERT-large": "bert-size",
    "BERT: pretrained on 3.3B word tokens (BookCorpus + English Wikipedia)": "bert-pretraining-data",
    # ResNet
    "ResNet: residual connections let networks of 100+ layers train": "resnet-skip",
    "ResNet: 3.57% error on ImageNet (ILSVRC 2015 classification)": "resnet-imagenet",
    "ResNet: shortcut connections can be identity or projection": "resnet-shortcuts",
    "ResNet: bottleneck blocks reduce compute in deeper variants": "resnet-bottleneck",
    # Adam
    "Adam: adaptive moments combine momentum and RMSProp": "adam-moments",
    "Adam: default learning rate is 1e-3 (much higher than SGD's 1e-2 batch-size-scaled)": "adam-default-lr",
    "Adam: epsilon in the denominator prevents division by zero": "adam-epsilon",
    "Adam: weight decay should be decoupled (AdamW) for best results": "adam-adamw",
    # FlashAttention
    "FlashAttention: IO-aware exact attention via tiling": "flashattn-tiling",
    "FlashAttention: online softmax trick handles block-wise computation": "flashattn-online-softmax",
    "FlashAttention: requires GPU SRAM and CUDA; not portable": "flashattn-hardware",
    # LoRA
    "LoRA: low-rank decomposition of weight updates freezes W, trains A and B": "lora-decomposition",
    "LoRA: rank r=8 captures most of the fine-tuning quality": "lora-rank",
    "LoRA: adapters can be merged into the base model for zero-latency inference": "lora-merge",
    # Dropout
    "Dropout: randomly zero units during training to prevent co-adaptation": "dropout-definition",
    "Dropout: acts as an ensemble of exponentially many thinned networks": "dropout-ensemble",
    # Word2Vec
    "Word2Vec: skip-gram predicts context words from a center word": "w2v-skipgram",
    "Word2Vec: classic analogy example `king - man + woman ≈ queen`": "w2v-analogy",
    "Word2Vec: embedding dimension is a hyperparameter; typical values 50–300": "w2v-dim",
    # DQN
    "DQN: deep Q-network with experience replay and target network": "dqn-tricks",
    "DQN: outperformed a professional human player on 49 Atari games": "dqn-atari-results",
    "DQN: rewards clipped to {-1, 0, +1} to handle different game score scales": "dqn-reward-clipping",
    # PPO
    "PPO: clipped surrogate objective prevents destructively large policy updates": "ppo-clipped-objective",
    "PPO: the de facto RL algorithm for continuous and discrete control tasks": "ppo-default",
    "PPO: clipping epsilon controls how far the new policy can drift": "ppo-epsilon",
    # VAE
    "VAE: encoder-decoder with a probabilistic latent space": "vae-arch",
    "VAE: reparameterization trick makes sampling differentiable": "vae-reparameterization",
    "VAE: ELBO is the lower bound on log-likelihood being maximized": "vae-elbo",
    # BatchNorm
    "BatchNorm: normalize activations per mini-batch during training": "bn-formula",
    "BatchNorm: enables higher learning rates and reduces the importance of careful initialization": "bn-lr-benefit",
    # GELU
    "GELU: Gaussian Error Linear Unit activation used in transformers": "gelu-definition",
    "GELU: smoother than ReLU; stochastic regularization interpretation": "gelu-stochastic",
    # YOLO
    "YOLO: real-time object detection with a single neural network": "yolo-realtime",
    "YOLO: divides image into SxS grid; each cell predicts B boxes": "yolo-grid",
    # PER
    "PER: prioritize replay buffer samples by TD error magnitude": "per-td-error",
    "PER: rank-based vs proportional prioritization": None,
    # Distillation
    "Knowledge distillation: train a small model to match a large model's soft outputs": "dist-soft-labels",
    "Distillation: temperature T controls softness of probability distribution": "dist-temperature",
    "Distillation: why soft labels encode more than hard labels": "dist-dark-knowledge",
    # GAN
    "GAN: two networks trained in opposition -- generator and discriminator": "gan-arch",
    "GAN: training is unstable and prone to mode collapse": "gan-mode-collapse",
    "GAN: Wasserstein distance formulation gives more stable training (WGAN)": "gan-wgan",
    # LayerNorm / RMSNorm
    "LayerNorm: normalize across features within each example": "ln-definition",
    "LayerNorm vs BatchNorm: which to use when": "ln-vs-bn",
    "RMSNorm: layer norm without the mean-centering step": "rms-definition",
    "RMSNorm: why dropping mean-centering works": None,
    # MoE
    "Sparse MoE: route each token to top-k experts out of N total": "moe-routing",
    "MoE: load balancing loss prevents expert collapse": "moe-load-balancing",
    # SwiGLU
    "SwiGLU: gated activation in transformer FFN blocks": "swiglu-ffn",
    "SwiGLU: parameter-equivalent vs parameter-matched compared to ReLU/GELU": None,
    # RoPE / ALiBi / Mamba / DPO (no queries; still written, with derived slugs)
    "RoPE: rotary position embeddings applied to query and key vectors": "rope-definition",
    "RoPE: relative position emerges from absolute rotations": "rope-relative",
    "ALiBi: attention with linear biases (no position embeddings)": "alibi-definition",
    "Mamba: selective state-space model that competes with transformers": "mamba-arch",
    "Mamba: the selective mechanism makes the recurrence input-dependent": "mamba-selective",
    "DPO: direct preference optimization replaces RLHF's reward model + PPO": "dpo-loss",
    # General ML concepts
    "Softmax: turns logits into a probability distribution": "softmax-definition",
    "Cross-entropy loss: negative log-likelihood of the true class": "ce-definition",
    "Temperature in sampling: T<1 sharpens; T>1 flattens": "temperature-sampling",
    "Top-p (nucleus) sampling: sample from smallest set whose probabilities sum to p": "nucleus-sampling",
    "Beam search: keep top-k partial hypotheses at each step": "beam-search",
    "Gradient descent: the basic training loop": "gd-basics",
    "Learning rate: the most important hyperparameter": "lr-importance",
    "Weight initialization: Xavier and He (Kaiming)": "init-xavier-he",
    "Tokenization: BPE, WordPiece, and SentencePiece": "tok-bpe",
    "Tokenization: special tokens and their roles": "tok-special",
    "BLEU score: n-gram overlap between candidate and reference translations": "bleu-definition",
    "Perplexity: exponentiated cross-entropy of a probability distribution": "perplexity-definition",
    "Spearman correlation: rank-based measure of monotonic association": "spearman-definition",
    "AUC-ROC: area under the receiver operating characteristic curve": "auc-roc",
    "TF-IDF: term frequency times inverse document frequency": "tfidf-definition",
    "Cosine similarity: angle between two vectors, ignoring magnitude": "cosine-similarity",
    "Sparse vs dense retrieval: when each wins": "sparse-vs-dense",
}
