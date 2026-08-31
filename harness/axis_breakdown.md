### `grep`

| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |
|---|---|---|---|---|---|---|---|---|
| all | codebase | 191 | 17 | 0.776 | 0.839 | 0.833 | 0.718 | 0.059 |
| lexical | codebase | 87 | 0 | 0.885 | 0.943 | 0.931 | 0.833 | 0.000 |
| paraphrased | codebase | 87 | 0 | 0.667 | 0.736 | 0.736 | 0.602 | 0.000 |
| no_answer | codebase | 17 | 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.059 |
| entity | codebase | 165 | 17 | 0.770 | 0.838 | 0.831 | 0.716 | 0.059 |
| topical | codebase | 26 | 0 | 0.808 | 0.846 | 0.846 | 0.726 | 0.000 |
| lexical_entity | codebase | 74 | 0 | 0.878 | 0.946 | 0.932 | 0.840 | 0.000 |
| paraphrased_entity | codebase | 74 | 0 | 0.662 | 0.730 | 0.730 | 0.593 | 0.000 |
| lexical_topical | codebase | 13 | 0 | 0.923 | 0.923 | 0.923 | 0.795 | 0.000 |
| paraphrased_topical | codebase | 13 | 0 | 0.692 | 0.769 | 0.769 | 0.656 | 0.000 |
| all | papers | 267 | 13 | 0.878 | 0.906 | 0.906 | 0.804 | 0.000 |
| lexical | papers | 127 | 0 | 0.913 | 0.929 | 0.929 | 0.837 | 0.000 |
| paraphrased | papers | 127 | 0 | 0.843 | 0.882 | 0.882 | 0.770 | 0.000 |
| no_answer | papers | 13 | 13 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | papers | 189 | 13 | 0.886 | 0.920 | 0.920 | 0.816 | 0.000 |
| topical | papers | 78 | 0 | 0.859 | 0.872 | 0.872 | 0.776 | 0.000 |
| lexical_entity | papers | 88 | 0 | 0.920 | 0.932 | 0.932 | 0.840 | 0.000 |
| paraphrased_entity | papers | 88 | 0 | 0.852 | 0.909 | 0.909 | 0.791 | 0.000 |
| lexical_topical | papers | 39 | 0 | 0.897 | 0.923 | 0.923 | 0.830 | 0.000 |
| paraphrased_topical | papers | 39 | 0 | 0.821 | 0.821 | 0.821 | 0.722 | 0.000 |

### `fts`

| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |
|---|---|---|---|---|---|---|---|---|
| all | codebase | 191 | 17 | 0.943 | 0.966 | 0.960 | 0.887 | 0.118 |
| lexical | codebase | 87 | 0 | 0.966 | 0.977 | 0.971 | 0.928 | 0.000 |
| paraphrased | codebase | 87 | 0 | 0.920 | 0.954 | 0.948 | 0.846 | 0.000 |
| no_answer | codebase | 17 | 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.118 |
| entity | codebase | 165 | 17 | 0.959 | 0.980 | 0.973 | 0.904 | 0.118 |
| topical | codebase | 26 | 0 | 0.846 | 0.885 | 0.885 | 0.792 | 0.000 |
| lexical_entity | codebase | 74 | 0 | 0.973 | 0.986 | 0.980 | 0.936 | 0.000 |
| paraphrased_entity | codebase | 74 | 0 | 0.946 | 0.973 | 0.966 | 0.872 | 0.000 |
| lexical_topical | codebase | 13 | 0 | 0.923 | 0.923 | 0.923 | 0.885 | 0.000 |
| paraphrased_topical | codebase | 13 | 0 | 0.769 | 0.846 | 0.846 | 0.699 | 0.000 |
| all | papers | 267 | 13 | 0.961 | 0.980 | 0.980 | 0.921 | 0.000 |
| lexical | papers | 127 | 0 | 0.976 | 0.992 | 0.992 | 0.923 | 0.000 |
| paraphrased | papers | 127 | 0 | 0.945 | 0.969 | 0.969 | 0.919 | 0.000 |
| no_answer | papers | 13 | 13 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | papers | 189 | 13 | 0.955 | 0.983 | 0.983 | 0.920 | 0.000 |
| topical | papers | 78 | 0 | 0.974 | 0.974 | 0.974 | 0.923 | 0.000 |
| lexical_entity | papers | 88 | 0 | 0.966 | 0.989 | 0.989 | 0.927 | 0.000 |
| paraphrased_entity | papers | 88 | 0 | 0.943 | 0.977 | 0.977 | 0.913 | 0.000 |
| lexical_topical | papers | 39 | 0 | 1.000 | 1.000 | 1.000 | 0.915 | 0.000 |
| paraphrased_topical | papers | 39 | 0 | 0.949 | 0.949 | 0.949 | 0.932 | 0.000 |

### `dense_nomic`

| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |
|---|---|---|---|---|---|---|---|---|
| all | codebase | 191 | 17 | 0.966 | 0.977 | 0.974 | 0.946 | 0.000 |
| lexical | codebase | 87 | 0 | 0.989 | 1.000 | 0.994 | 0.958 | 0.000 |
| paraphrased | codebase | 87 | 0 | 0.943 | 0.954 | 0.954 | 0.933 | 0.000 |
| no_answer | codebase | 17 | 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | codebase | 165 | 17 | 0.966 | 0.980 | 0.976 | 0.951 | 0.000 |
| topical | codebase | 26 | 0 | 0.962 | 0.962 | 0.962 | 0.917 | 0.000 |
| lexical_entity | codebase | 74 | 0 | 0.986 | 1.000 | 0.993 | 0.960 | 0.000 |
| paraphrased_entity | codebase | 74 | 0 | 0.946 | 0.959 | 0.959 | 0.942 | 0.000 |
| lexical_topical | codebase | 13 | 0 | 1.000 | 1.000 | 1.000 | 0.949 | 0.000 |
| paraphrased_topical | codebase | 13 | 0 | 0.923 | 0.923 | 0.923 | 0.885 | 0.000 |
| all | papers | 267 | 13 | 0.988 | 1.000 | 1.000 | 0.955 | 0.000 |
| lexical | papers | 127 | 0 | 0.992 | 1.000 | 1.000 | 0.965 | 0.000 |
| paraphrased | papers | 127 | 0 | 0.984 | 1.000 | 1.000 | 0.944 | 0.000 |
| no_answer | papers | 13 | 13 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | papers | 189 | 13 | 0.994 | 1.000 | 1.000 | 0.969 | 0.000 |
| topical | papers | 78 | 0 | 0.974 | 1.000 | 1.000 | 0.922 | 0.000 |
| lexical_entity | papers | 88 | 0 | 1.000 | 1.000 | 1.000 | 0.983 | 0.000 |
| paraphrased_entity | papers | 88 | 0 | 0.989 | 1.000 | 1.000 | 0.955 | 0.000 |
| lexical_topical | papers | 39 | 0 | 0.974 | 1.000 | 1.000 | 0.925 | 0.000 |
| paraphrased_topical | papers | 39 | 0 | 0.974 | 1.000 | 1.000 | 0.920 | 0.000 |

### `dense_bge`

| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |
|---|---|---|---|---|---|---|---|---|
| all | codebase | 191 | 17 | 0.989 | 0.989 | 0.989 | 0.971 | 0.000 |
| lexical | codebase | 87 | 0 | 1.000 | 1.000 | 1.000 | 0.977 | 0.000 |
| paraphrased | codebase | 87 | 0 | 0.977 | 0.977 | 0.977 | 0.966 | 0.000 |
| no_answer | codebase | 17 | 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | codebase | 165 | 17 | 0.986 | 0.986 | 0.986 | 0.970 | 0.000 |
| topical | codebase | 26 | 0 | 1.000 | 1.000 | 1.000 | 0.981 | 0.000 |
| lexical_entity | codebase | 74 | 0 | 1.000 | 1.000 | 1.000 | 0.973 | 0.000 |
| paraphrased_entity | codebase | 74 | 0 | 0.973 | 0.973 | 0.973 | 0.966 | 0.000 |
| lexical_topical | codebase | 13 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| paraphrased_topical | codebase | 13 | 0 | 1.000 | 1.000 | 1.000 | 0.962 | 0.000 |
| all | papers | 267 | 13 | 0.980 | 0.992 | 0.992 | 0.947 | 0.000 |
| lexical | papers | 127 | 0 | 0.992 | 0.992 | 0.992 | 0.957 | 0.000 |
| paraphrased | papers | 127 | 0 | 0.969 | 0.992 | 0.992 | 0.938 | 0.000 |
| no_answer | papers | 13 | 13 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | papers | 189 | 13 | 0.989 | 1.000 | 1.000 | 0.970 | 0.000 |
| topical | papers | 78 | 0 | 0.962 | 0.974 | 0.974 | 0.896 | 0.000 |
| lexical_entity | papers | 88 | 0 | 1.000 | 1.000 | 1.000 | 0.975 | 0.000 |
| paraphrased_entity | papers | 88 | 0 | 0.977 | 1.000 | 1.000 | 0.964 | 0.000 |
| lexical_topical | papers | 39 | 0 | 0.974 | 0.974 | 0.974 | 0.915 | 0.000 |
| paraphrased_topical | papers | 39 | 0 | 0.949 | 0.974 | 0.974 | 0.878 | 0.000 |

### `dense_tfidf`

| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |
|---|---|---|---|---|---|---|---|---|
| all | codebase | 191 | 17 | 0.885 | 0.914 | 0.908 | 0.781 | 0.059 |
| lexical | codebase | 87 | 0 | 0.954 | 0.966 | 0.954 | 0.847 | 0.000 |
| paraphrased | codebase | 87 | 0 | 0.816 | 0.862 | 0.862 | 0.714 | 0.000 |
| no_answer | codebase | 17 | 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.059 |
| entity | codebase | 165 | 17 | 0.885 | 0.919 | 0.912 | 0.770 | 0.059 |
| topical | codebase | 26 | 0 | 0.885 | 0.885 | 0.885 | 0.840 | 0.000 |
| lexical_entity | codebase | 74 | 0 | 0.959 | 0.973 | 0.959 | 0.834 | 0.000 |
| paraphrased_entity | codebase | 74 | 0 | 0.811 | 0.865 | 0.865 | 0.707 | 0.000 |
| lexical_topical | codebase | 13 | 0 | 0.923 | 0.923 | 0.923 | 0.923 | 0.000 |
| paraphrased_topical | codebase | 13 | 0 | 0.846 | 0.846 | 0.846 | 0.756 | 0.000 |
| all | papers | 267 | 13 | 0.902 | 0.953 | 0.953 | 0.831 | 0.000 |
| lexical | papers | 127 | 0 | 0.906 | 0.953 | 0.953 | 0.822 | 0.000 |
| paraphrased | papers | 127 | 0 | 0.898 | 0.953 | 0.953 | 0.839 | 0.000 |
| no_answer | papers | 13 | 13 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | papers | 189 | 13 | 0.909 | 0.955 | 0.955 | 0.845 | 0.000 |
| topical | papers | 78 | 0 | 0.885 | 0.949 | 0.949 | 0.797 | 0.000 |
| lexical_entity | papers | 88 | 0 | 0.909 | 0.955 | 0.955 | 0.827 | 0.000 |
| paraphrased_entity | papers | 88 | 0 | 0.909 | 0.955 | 0.955 | 0.864 | 0.000 |
| lexical_topical | papers | 39 | 0 | 0.897 | 0.949 | 0.949 | 0.812 | 0.000 |
| paraphrased_topical | papers | 39 | 0 | 0.872 | 0.949 | 0.949 | 0.783 | 0.000 |

### `hybrid`

| Axis | Domain | N | N(no-ans) | P@3 | P@5 | R@5 | MRR | no-ans zero-rate |
|---|---|---|---|---|---|---|---|---|
| all | codebase | 191 | 17 | 0.977 | 0.994 | 0.991 | 0.930 | 0.000 |
| lexical | codebase | 87 | 0 | 0.989 | 1.000 | 0.994 | 0.953 | 0.000 |
| paraphrased | codebase | 87 | 0 | 0.966 | 0.989 | 0.989 | 0.907 | 0.000 |
| no_answer | codebase | 17 | 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | codebase | 165 | 17 | 0.986 | 0.993 | 0.990 | 0.942 | 0.000 |
| topical | codebase | 26 | 0 | 0.923 | 1.000 | 1.000 | 0.863 | 0.000 |
| lexical_entity | codebase | 74 | 0 | 1.000 | 1.000 | 0.993 | 0.964 | 0.000 |
| paraphrased_entity | codebase | 74 | 0 | 0.973 | 0.986 | 0.986 | 0.919 | 0.000 |
| lexical_topical | codebase | 13 | 0 | 0.923 | 1.000 | 1.000 | 0.891 | 0.000 |
| paraphrased_topical | codebase | 13 | 0 | 0.923 | 1.000 | 1.000 | 0.836 | 0.000 |
| all | papers | 267 | 13 | 0.988 | 1.000 | 1.000 | 0.954 | 0.000 |
| lexical | papers | 127 | 0 | 1.000 | 1.000 | 1.000 | 0.961 | 0.000 |
| paraphrased | papers | 127 | 0 | 0.976 | 1.000 | 1.000 | 0.947 | 0.000 |
| no_answer | papers | 13 | 13 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| entity | papers | 189 | 13 | 0.989 | 1.000 | 1.000 | 0.963 | 0.000 |
| topical | papers | 78 | 0 | 0.987 | 1.000 | 1.000 | 0.933 | 0.000 |
| lexical_entity | papers | 88 | 0 | 1.000 | 1.000 | 1.000 | 0.975 | 0.000 |
| paraphrased_entity | papers | 88 | 0 | 0.977 | 1.000 | 1.000 | 0.951 | 0.000 |
| lexical_topical | papers | 39 | 0 | 1.000 | 1.000 | 1.000 | 0.927 | 0.000 |
| paraphrased_topical | papers | 39 | 0 | 0.974 | 1.000 | 1.000 | 0.938 | 0.000 |

