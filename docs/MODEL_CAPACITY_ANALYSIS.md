# Parameter Scale Analysis: 1,350 → 23,686

## Architectural Comparison

### Original (1,350 params)
Input: [198, 13, 1]
├── Conv2D(8, 3×3)      → 8×(3×3×1) + 8 = 80
├── MaxPool2D(2×2)      → 0
├── Conv2D(16, 3×3)     → 16×(3×3×8) + 16 = 1,168
├── GlobalAvgPool2D     → 0
└── Dense(6)            → 16×6 + 6 = 102
Total trainable: ~1,350

### Enhanced (23,686 params)
Input: [198, 20, 1]
├── Conv2D(16, 3×3)     → 16×(3×3×1) + 16 = 160
├── MaxPool2D(2×2)      → 0
├── Conv2D(32, 3×3)     → 32×(3×3×16) + 32 = 4,640
├── Conv2D(64, 3×3)     → 64×(3×3×32) + 64 = 18,496
├── GlobalAvgPool2D     → 0
└── Dense(6)            → 64×6 + 6 = 390
Total trainable: ~23,686

## Key Modifications Driving Improvement

### 1. Feature Dimensionality (mel_bins 40→64, mfcc 13→20)
- **Mathematical impact**: The DCT projection matrix in features.py:21-24 now maps 64 mel bins → 20 coefficients instead of 40→13.
- **Enhancement**: More mel bins preserve finer spectral detail in the 20-7600 Hz range. Each additional bin reduces inter-bin correlation leakage. The 7 additional MFCCs capture higher-order spectral envelope variations critical for distinguishing similar phonemes in voice commands.
- **Parameter effect**: Input shape changes from [198,13,1] to [198,20,1], increasing first-layer weight tensor from 1×3×3×8 to 1×3×3×16.

### 2. Convolutional Depth (2→3 layers)
- **Original**: Conv(8)→Pool→Conv(16)→GAP→Dense(6)
- **Enhanced**: Conv(16)→Pool→Conv(32)→Conv(64)→GAP→Dense(6)
- **Receptive field growth**: The added third conv layer allows hierarchical feature composition:
  - Layer 1 (16 filters): Detects edge/texture patterns in time-frequency space
  - Layer 2 (32 filters): Combines layer-1 features into mid-level spectral shapes
  - Layer 3 (64 filters): Composes mid-level features into high-level phonetic/articulatory patterns
- **Parameter distribution**: 18,496 params (78%) concentrated in the final conv layer, where feature maps are richest.

### 3. Filter Count Scaling (8→16, 16→32, +64)
- **Capacity scaling law**: Total conv params ≈ Σ(Fᵢ × Fᵢ₋₁ × K²) where F₀ = input channels.
- **Enhanced architecture**:
  - Layer 1: 16 filters × 1 input channel × 9 weights = 144 weights + 16 biases
  - Layer 2: 32 × 16 × 9 = 4,608 + 32
  - Layer 3: 64 × 32 × 9 = 18,432 + 64
- **Representation capacity**: The 64-filter layer can encode 64 distinct spectral-temporal patterns simultaneously, compared to just 16 in the original final layer.

### 4. MaxPooling Placement
- Single 2×2 pool after first conv reduces spatial dimensions from [198,20] to [99,20].
- This provides translation invariance early while preserving sufficient resolution for deeper layers.

### 5. Regularization via Augmentation
- **Noise injection** (σ=0.01): Forces robustness to sensor noise and quantization error.
- **Random gain** (0.8-1.2): Compensates for recording amplitude variations.
- **Time shift** (±5 frames): Provides temporal invariance without altering pitch.
- **Class weighting**: Inverse frequency balancing prevents majority-class bias toward "silence"/"unknown".

### 6. Optimization Enhancements
- **EarlyStopping patience 8→20**: Allows continued training when validation metrics plateau.
- **ReduceLROnPlateau** (factor=0.5, patience=5): Adaptive learning rate decay escapes local minima by reducing LR when validation loss stagnates.

## Expected Performance Impact

| Metric | Original | Enhanced | Improvement Mechanism |
|--------|----------|----------|----------------------|
| Train capacity | ~1,350 | ~23,686 | 17.5× increase in decision regions |
| Spectral resolution | 13 MFCCs | 20 MFCCs | 54% more envelope descriptors |
| Nonlinear depth | 2 conv layers | 3 conv layers | Composes features 3 levels deep |
| Generalization | Prone to overfitting | Augmentation + class weights | Regularization reduces small-dataset memorization |

The 17.5× parameter increase is primarily driven by the third convolutional layer (18,496 params), which enables learning hierarchical representations from raw spectral patterns → phonetic features → command-specific signatures. Combined with richer input features and adaptive optimization, this architecture is significantly better suited to the 6-class voice command task.