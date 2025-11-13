# Extensibility: Multiple Methods

The survey system is designed to support **any number of methods** through pairwise comparisons.

## How It Works

Each line in `image_pairs.txt` represents one pairwise comparison. The method names can be different for each comparison, allowing you to test any combination of methods.

## Example: 3 Methods

If you have 3 methods (A, B, C), you need **3 comparisons per prompt**:

```
# Prompt 1: Mountain landscape
A serene mountain landscape	Method-A	Method-B	img_a1.jpg	img_b1.jpg
A serene mountain landscape	Method-A	Method-C	img_a1.jpg	img_c1.jpg
A serene mountain landscape	Method-B	Method-C	img_b1.jpg	img_c1.jpg

# Prompt 2: Futuristic city  
A futuristic city	Method-A	Method-B	img_a2.jpg	img_b2.jpg
A futuristic city	Method-A	Method-C	img_a2.jpg	img_c2.jpg
A futuristic city	Method-B	Method-C	img_b2.jpg	img_c2.jpg
```

## Scaling to N Methods

| Methods | Comparisons per Prompt | Total with 10 Prompts |
|---------|------------------------|------------------------|
| 2       | 1                      | 10                     |
| 3       | 3                      | 30                     |
| 4       | 6                      | 60                     |
| 5       | 10                     | 100                    |
| 6       | 15                     | 150                    |

Formula: **C(N,2) = N×(N-1)/2** comparisons per prompt

## Helper Script

Use `generate_pairs.py` to automatically generate all pairwise combinations:

```bash
# 1. Edit generate_pairs.py:
#    - Set your METHODS (names and base URLs)
#    - Set your PROMPTS

# 2. Generate image_pairs.txt:
python generate_pairs.py > image_pairs.txt

# 3. Verify:
head -20 image_pairs.txt
```

## Admin View Benefits

The admin interface automatically groups results by method name:

```
Method Preferences (Image Quality):
  Method-A: 45, Method-B: 38, Method-C: 27

Method Preferences (Prompt Adherence):
  Method-A: 52, Method-B: 34, Method-C: 24
```

This works automatically regardless of how many methods you have!

## CSV Export

The CSV export includes:
- `method_a`, `method_b` - Which methods were compared
- `better_image` - User's UI choice (A or B)
- `preferred_method_image` - Actual method name user preferred
- `preferred_method_prompt` - Method that better matched prompt

This makes it easy to analyze results across all method combinations.

## Best Practices

### 1. **Consistent Ordering**
Use alphabetical or consistent ordering for method pairs to avoid confusion:
```
# Good: Alphabetical
Method-A vs Method-B
Method-A vs Method-C
Method-B vs Method-C

# Also fine: Baseline first
Baseline vs Method-1
Baseline vs Method-2
Method-1 vs Method-2
```

### 2. **Balanced Comparisons**
Make sure each method appears roughly equally often:
- With 3 methods, each appears in 2 comparisons per prompt ✓
- With 4 methods, each appears in 3 comparisons per prompt ✓

### 3. **Survey Length**
Consider participant fatigue:
- 30 comparisons ≈ 10-15 minutes
- 60 comparisons ≈ 20-30 minutes
- 100 comparisons ≈ 35-50 minutes

You might want fewer prompts with more methods:
- 10 prompts × 3 methods = 30 comparisons (good!)
- 5 prompts × 6 methods = 75 comparisons (getting long)
- 3 prompts × 10 methods = 135 comparisons (too long!)

### 4. **Method Naming**
Use descriptive names that don't reveal which is "better":
```
# Good:
Method-A, Method-B, Method-C
Model-1, Model-2, Model-3
Approach-X, Approach-Y, Approach-Z

# Avoid revealing names:
Baseline, Improved, Best
Old, New
Ours, Theirs
```

## Technical Details

### No Code Changes Needed

The system is already fully extensible:
- ✅ Image loading handles any method names
- ✅ Randomization preserves method names correctly
- ✅ Database stores method_a and method_b
- ✅ Admin view aggregates by method name
- ✅ CSV export includes all method information

### Database Schema

```sql
CREATE TABLE survey_responses (
    ...
    method_a TEXT,        -- First method in comparison
    method_b TEXT,        -- Second method in comparison
    better_image TEXT,    -- User's choice: "A" or "B"
    preferred_method_image TEXT,  -- Computed: actual method name
    ...
);
```

The `preferred_method_image` is computed as:
```sql
CASE 
    WHEN better_image = 'A' THEN method_a
    WHEN better_image = 'B' THEN method_b
END
```

This works for any method names!

## Example Analysis

With 4 methods over 10 prompts (60 comparisons total):

```python
import pandas as pd

df = pd.read_csv('survey_results.csv')

# Count wins per method
image_quality = df['preferred_method_image'].value_counts()
prompt_match = df['preferred_method_prompt'].value_counts()

print("Image Quality Rankings:")
print(image_quality)

print("\nPrompt Adherence Rankings:")
print(prompt_match)

# Pairwise comparison matrix
pivot = df.pivot_table(
    index='method_a',
    columns='method_b', 
    values='preferred_method_image',
    aggfunc='count'
)
print("\nPairwise Comparison Counts:")
print(pivot)
```

## Summary

✅ **The system is already extensible!**  
✅ No code changes needed for N methods  
✅ Just edit `image_pairs.txt` with all pairs  
✅ Use `generate_pairs.py` to automate generation  
✅ Admin view automatically handles any number of methods  
✅ CSV export ready for advanced analysis

