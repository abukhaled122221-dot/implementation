import math

class RecommendationAgent:
    def __init__(self):
        # Weights for the 8 criteria (must sum to 1)
        self.weights = {
            'premium': 0.20,
            'coverage': 0.20,
            'coverage_to_price': 0.15,
            'deductible': 0.10,
            'addons': 0.10,
            'fit': 0.10,
            'reliability': 0.10,
            'availability': 0.05
        }
        # We'll compute min/max for normalization across the quote set
        self.norm_stats = {}

    def _compute_norm_stats(self, quotes):
        """Compute min and max for each criterion across quotes for normalization."""
        if not quotes:
            return
        # Initialize stats
        self.norm_stats = {
            'premium': {'min': float('inf'), 'max': float('-inf')},
            'deductible': {'min': float('inf'), 'max': float('-inf')},
            # For coverage score we'll compute per quote, not needed min/max across quotes? We'll compute coverage score directly.
            # For coverage-to-price we'll compute ratio then normalize.
            # For addons count we'll compute count.
            # For fit we'll compute per quote (0 or 1) so min/max maybe 0,1.
            # For reliability we have raw score.
        }
        # First pass to collect min/max for premium and deductible
        for q in quotes:
            p = q.get('premium', 0)
            d = q.get('deductible', 0)
            if p < self.norm_stats['premium']['min']:
                self.norm_stats['premium']['min'] = p
            if p > self.norm_stats['premium']['max']:
                self.norm_stats['premium']['max'] = p
            if d < self.norm_stats['deductible']['min']:
                self.norm_stats['deductible']['min'] = d
            if d > self.norm_stats['deductible']['max']:
                self.norm_stats['deductible']['max'] = d

        # If min == max, avoid division by zero later
        if self.norm_stats['premium']['min'] == self.norm_stats['premium']['max']:
            self.norm_stats['premium']['max'] = self.norm_stats['premium']['min'] + 1
        if self.norm_stats['deductible']['min'] == self.norm_stats['deductible']['max']:
            self.norm_stats['deductible']['max'] = self.norm_stats['deductible']['min'] + 1

    def _normalize_premium(self, premium):
        """Lower premium -> higher score."""
        min_p = self.norm_stats['premium']['min']
        max_p = self.norm_stats['premium']['max']
        if max_p == min_p:
            return 0.5
        return (max_p - premium) / (max_p - min_p)

    def _normalize_deductible(self, deductible):
        """Lower deductible -> higher score."""
        min_d = self.norm_stats['deductible']['min']
        max_d = self.norm_stats['deductible']['max']
        if max_d == min_d:
            return 0.5
        return (max_d - deductible) / (max_d - min_d)

    def _coverage_score(self, q):
        """Compute coverage score based on type and scope."""
        coverage_type = q.get('coverage_type', 'TPL')
        coverage_scope = q.get('coverage_scope', [])
        # Base score for type
        type_score = 1.0 if coverage_type == 'Comprehensive' else 0.5
        # Scope: number of risks covered relative to max possible
        # Define max possible risks we consider: ['collision', 'theft', 'fire', 'natural_events', 'third_party']?
        # We'll just use length of scope list, normalize by max observed later? Simpler: give fixed based on type.
        # We'll just return type_score for simplicity.
        return type_score

    def _coverage_to_price_ratio(self, q):
        """Protection / price. Protection we can take as coverage score (0-1)."""
        coverage = self._coverage_score(q)
        premium = q.get('premium', 1)
        if premium == 0:
            return 0
        return coverage / premium

    def _normalize_coverage_to_price(self, ratio):
        # We'll normalize across quotes later using min/max; we'll compute min/max for this ratio.
        pass

    def _addons_score(self, q):
        """Number of add-ons, normalized by max add-ons observed."""
        addons = q.get('add_ons', [])
        return len(addons)

    def _fit_score(self, q, customer_data):
        """Fit to driver and vehicle profile."""
        vehicle_value = customer_data.get('vehicle_value', 50000)
        coverage_type = q.get('coverage_type', 'TPL')
        # Simple rule: if vehicle is expensive (>100k) comprehensive is better fit; else TPL is fine.
        if vehicle_value > 100000:
            return 1.0 if coverage_type == 'Comprehensive' else 0.5
        else:
            return 1.0 if coverage_type == 'TPL' else 0.5

    def _reliability_score(self, q):
        """Provider reliability (0-10) -> normalize to 0-1."""
        rel = q.get('provider_reliability', 0)
        return rel / 10.0  # assuming max 10

    def _availability_score(self, q):
        """Availability and freshness: assume all live -> 1.0"""
        return 1.0 if q.get('availability', False) else 0.0

    def compute_scores(self, quotes, customer_data):
        """Compute suitability score for each quote."""
        if not quotes:
            return []
        # Compute normalization stats for premium and deductible
        self._compute_norm_stats(quotes)
        # We'll also need min/max for coverage_to_price ratio and addons count across quotes
        ratios = []
        addon_counts = []
        for q in quotes:
            ratio = self._coverage_to_price_ratio(q)
            ratios.append(ratio)
            addon_counts.append(len(q.get('add_ons', [])))
        # Compute min/max for ratios and addon_counts
        if ratios:
            min_ratio = min(ratios)
            max_ratio = max(ratios)
            if max_ratio == min_ratio:
                max_ratio = min_ratio + 1
        else:
            min_ratio = 0
            max_ratio = 1
        if addon_counts:
            min_addons = min(addon_counts)
            max_addons = max(addon_counts)
            if max_addons == min_addons:
                max_addons = min_addons + 1
        else:
            min_addons = 0
            max_addons = 1

        scored_quotes = []
        for q in quotes:
            # Compute each criterion score (0-1)
            s1 = self._normalize_premium(q.get('premium', 0))
            s2 = self._coverage_score(q)  # already 0-1 scale? we made it 0.5 or 1.0
            # Normalize s2 to 0-1? It's already 0.5 or 1.0, fine.
            s3_ratio = self._coverage_to_price_ratio(q)
            s3 = (s3_ratio - min_ratio) / (max_ratio - min_ratio) if max_ratio != min_ratio else 0.5
            s4 = self._normalize_deductible(q.get('deductible', 0))
            s5_num = len(q.get('add_ons', []))
            s5 = (s5_num - min_addons) / (max_addons - min_addons) if max_addons != min_addons else 0.5
            s6 = self._fit_score(q, customer_data)
            s7 = self._reliability_score(q)
            s8 = self._availability_score(q)

            # Weighted sum
            total = (self.weights['premium'] * s1 +
                     self.weights['coverage'] * s2 +
                     self.weights['coverage_to_price'] * s3 +
                     self.weights['deductible'] * s4 +
                     self.weights['addons'] * s5 +
                     self.weights['fit'] * s6 +
                     self.weights['reliability'] * s7 +
                     self.weights['availability'] * s8)

            scored_quotes.append({
                'quote': q,
                'score': total,
                'breakdown': {
                    'premium': s1,
                    'coverage': s2,
                    'coverage_to_price': s3,
                    'deductible': s4,
                    'addons': s5,
                    'fit': s6,
                    'reliability': s7,
                    'availability': s8,
                    'weighted_premium': self.weights['premium'] * s1,
                    'weighted_coverage': self.weights['coverage'] * s2,
                    'weighted_coverage_to_price': self.weights['coverage_to_price'] * s3,
                    'weighted_deductible': self.weights['deductible'] * s4,
                    'weighted_addons': self.weights['addons'] * s5,
                    'weighted_fit': self.weights['fit'] * s6,
                    'weighted_reliability': self.weights['reliability'] * s7,
                    'weighted_availability': self.weights['availability'] * s8
                }
            })
        return scored_quotes

    def recommend(self, quotes, customer_data):
        """Return the highest scoring quote and its breakdown."""
        scored = self.compute_scores(quotes, customer_data)
        if not scored:
            return None, None
        # Sort by score descending
        scored.sort(key=lambda x: x['score'], reverse=True)
        best = scored[0]
        return best['quote'], best['breakdown']

# Example usage (for testing)
if __name__ == "__main__":
    # Mock quotes (as would come from Agent 1)
    mock_quotes = [
        {
            "company": "Tawuniya",
            "premium": 483,
            "coverage_type": "TPL",
            "deductible": 500,
            "add_ons": ["roadside_assistance"],
            "coverage_scope": ["third_party"],
            "provider_reliability": 9.0,
            "availability": True
        },
        {
            "company": "Medgulf",
            "premium": 469,
            "coverage_type": "TPL",
            "deductible": 550,
            "add_ons": [],
            "coverage_scope": ["third_party"],
            "provider_reliability": 7.0,
            "availability": True
        },
        {
            "company": "ACIG",
            "premium": 428,
            "coverage_type": "TPL",
            "deductible": 700,
            "add_ons": [],
            "coverage_scope": ["third_party"],
            "provider_reliability": 6.0,
            "availability": True
        },
        {
            "company": "Takaful Al-Rajhi",
            "premium": 507,
            "coverage_type": "TPL",
            "deductible": 600,
            "add_ons": ["roadside_assistance"],
            "coverage_scope": ["third_party"],
            "provider_reliability": 9.5,
            "availability": True
        }
    ]
    customer_data = {
        "vehicle_value": 70000,
        "driver_age": 35
    }
    agent2 = RecommendationAgent()
    quote, breakdown = agent2.recommend(mock_quotes, customer_data)
    print("Recommended quote:")
    print(quote)
    print("\nScore breakdown:")
    for k, v in breakdown.items():
        print(f"{k}: {v}")