#include "strategy_planner.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>

namespace {

constexpr double kPriceGuardMultiplier = 1.25;
constexpr std::size_t kMaxCandidatePaths = 4000;

struct RawSegmentStats {
    std::vector<double> prices;
    std::vector<int> durations;
    std::string data_source;
};

std::string transport_key(TransportType transport_type) {
    return transport_type == TransportType::Flight ? "flight" : "train";
}

std::string segment_key(
    const std::string& from_city_code,
    const std::string& to_city_code,
    TransportType transport_type
) {
    return from_city_code + "|" + to_city_code + "|" + transport_key(transport_type);
}

std::string pair_key(const std::string& from_city_code, const std::string& to_city_code) {
    return from_city_code + "|" + to_city_code;
}

double round_to(double value, int digits) {
    const double factor = std::pow(10.0, digits);
    return std::round(value * factor) / factor;
}

double median_double(std::vector<double> values) {
    if (values.empty()) {
        return 0.0;
    }
    std::sort(values.begin(), values.end());
    const std::size_t middle = values.size() / 2;
    if (values.size() % 2 == 1) {
        return values[middle];
    }
    return (values[middle - 1] + values[middle]) / 2.0;
}

double mean_double(const std::vector<double>& values) {
    if (values.empty()) {
        return 0.0;
    }
    return std::accumulate(values.begin(), values.end(), 0.0) / values.size();
}

double coefficient_stability(const std::vector<double>& values) {
    if (values.size() <= 1) {
        return 1.0;
    }
    const double mean = mean_double(values);
    if (mean <= 0.0) {
        return 0.0;
    }
    double variance = 0.0;
    for (double value : values) {
        variance += (value - mean) * (value - mean);
    }
    variance /= values.size();
    const double coefficient = std::sqrt(variance) / mean;
    return round_to(std::max(0.0, 1.0 - coefficient), 4);
}

double coefficient_stability(const std::vector<int>& values) {
    std::vector<double> converted;
    converted.reserve(values.size());
    for (int value : values) {
        converted.push_back(static_cast<double>(value));
    }
    return coefficient_stability(converted);
}

int median_int(std::vector<int> values) {
    if (values.empty()) {
        return 0;
    }
    std::sort(values.begin(), values.end());
    const std::size_t middle = values.size() / 2;
    if (values.size() % 2 == 1) {
        return values[middle];
    }
    return static_cast<int>(std::round((values[middle - 1] + values[middle]) / 2.0));
}

bool transport_allowed(TransportType transport_type, bool allow_flight, bool allow_train) {
    return (transport_type == TransportType::Flight && allow_flight) ||
           (transport_type == TransportType::Train && allow_train);
}

std::string price_level(double price, double baseline) {
    if (baseline > 0.0) {
        const double ratio = price / baseline;
        if (ratio <= 1.05) {
            return "low";
        }
        if (ratio <= kPriceGuardMultiplier) {
            return "medium";
        }
        return "high";
    }
    if (price <= 350.0) {
        return "low";
    }
    if (price <= 800.0) {
        return "medium";
    }
    return "high";
}

std::string duration_level(int minutes) {
    if (minutes <= 180) {
        return "short";
    }
    if (minutes <= 420) {
        return "medium";
    }
    return "long";
}

std::string frequency_level(double score) {
    if (score >= 0.66) {
        return "high";
    }
    if (score >= 0.33) {
        return "medium";
    }
    return "low";
}

double inverse_component(double value, double multiplier) {
    return multiplier / std::max(value, 1.0);
}

std::unordered_set<std::string> to_set(const std::vector<std::string>& values) {
    return std::unordered_set<std::string>(values.begin(), values.end());
}

bool contains_all(
    const std::unordered_set<std::string>& available,
    const std::unordered_set<std::string>& required
) {
    for (const auto& value : required) {
        if (available.count(value) == 0) {
            return false;
        }
    }
    return true;
}

std::vector<std::string> reason_codes(
    int transfer_count,
    double estimated_price,
    double direct_price,
    double service_score
) {
    std::vector<std::string> reasons{"segment_confirmable"};
    if (transfer_count == 0) {
        reasons.push_back("direct_available");
    } else if (direct_price > 0.0 && estimated_price <= direct_price * 1.1) {
        reasons.push_back("near_direct_cost");
    } else if (transfer_count > 0) {
        reasons.push_back("transfer_option");
    }
    if (service_score >= 0.65) {
        reasons.push_back("high_service_frequency");
    }
    return reasons;
}

}  // namespace

void TrafficGraph::add_edge(const SegmentAvailability& edge) {
    const std::string key = pair_key(edge.from_city_code, edge.to_city_code);
    segments_by_pair_[key].push_back(edge);
    auto& adjacent = adjacency_[edge.from_city_code];
    if (std::find(adjacent.begin(), adjacent.end(), edge.to_city_code) == adjacent.end()) {
        adjacent.push_back(edge.to_city_code);
        std::sort(adjacent.begin(), adjacent.end());
    }
}

std::vector<std::string> TrafficGraph::adjacent_cities(
    const std::string& city_code,
    bool allow_flight,
    bool allow_train
) const {
    std::vector<std::string> results;
    const auto iterator = adjacency_.find(city_code);
    if (iterator == adjacency_.end()) {
        return results;
    }

    for (const auto& to_city_code : iterator->second) {
        if (!segment_options(city_code, to_city_code, allow_flight, allow_train).empty()) {
            results.push_back(to_city_code);
        }
    }
    return results;
}

std::vector<SegmentAvailability> TrafficGraph::segment_options(
    const std::string& from_city_code,
    const std::string& to_city_code,
    bool allow_flight,
    bool allow_train
) const {
    const auto iterator = segments_by_pair_.find(pair_key(from_city_code, to_city_code));
    if (iterator == segments_by_pair_.end()) {
        return {};
    }

    std::vector<SegmentAvailability> results;
    for (const auto& edge : iterator->second) {
        if (transport_allowed(edge.transport_type, allow_flight, allow_train)) {
            results.push_back(edge);
        }
    }
    std::sort(
        results.begin(),
        results.end(),
        [](const SegmentAvailability& left, const SegmentAvailability& right) {
            if (left.estimated_price != right.estimated_price) {
                return left.estimated_price < right.estimated_price;
            }
            if (left.estimated_duration_minutes != right.estimated_duration_minutes) {
                return left.estimated_duration_minutes < right.estimated_duration_minutes;
            }
            return transport_key(left.transport_type) < transport_key(right.transport_type);
        }
    );
    return results;
}

TrafficGraph TrafficGraphBuilder::build(
    const std::vector<StrategyStationInput>& stations,
    const std::vector<StrategyRouteInput>& routes
) {
    std::unordered_map<std::string, std::string> station_city;
    for (const auto& station : stations) {
        station_city[station.code] = station.city_code;
    }

    std::unordered_map<std::string, RawSegmentStats> raw_stats;
    for (const auto& route : routes) {
        const auto from_iterator = station_city.find(route.from_station);
        const auto to_iterator = station_city.find(route.to_station);
        if (from_iterator == station_city.end() || to_iterator == station_city.end()) {
            continue;
        }
        const std::string from_city_code = from_iterator->second;
        const std::string to_city_code = to_iterator->second;
        const std::string key = segment_key(from_city_code, to_city_code, route.transport_type);
        auto& stats = raw_stats[key];
        stats.prices.push_back(route.price);
        stats.durations.push_back(route.duration_minutes);
        if (stats.data_source.empty()) {
            stats.data_source = route.data_source.empty() ? "mock_graph" : route.data_source;
        }
    }

    TrafficGraph graph;
    for (const auto& entry : raw_stats) {
        std::stringstream key_stream(entry.first);
        std::string from_city_code;
        std::string to_city_code;
        std::string transport_text;
        std::getline(key_stream, from_city_code, '|');
        std::getline(key_stream, to_city_code, '|');
        std::getline(key_stream, transport_text, '|');

        const auto& stats = entry.second;
        const int sample_count = static_cast<int>(stats.prices.size());
        const double service_score = std::min(1.0, sample_count / 12.0);
        const double availability_score = std::min(1.0, sample_count / 6.0);
        const double confidence = std::min(0.98, 0.45 + sample_count * 0.045);

        graph.add_edge(SegmentAvailability{
            from_city_code,
            to_city_code,
            transport_text == "flight" ? TransportType::Flight : TransportType::Train,
            sample_count,
            round_to(median_double(stats.prices), 2),
            median_int(stats.durations),
            round_to(service_score, 4),
            round_to(availability_score, 4),
            round_to(confidence, 4),
            coefficient_stability(stats.prices),
            coefficient_stability(stats.durations),
            stats.data_source.empty() ? "mock_graph" : stats.data_source,
        });
    }

    return graph;
}

std::vector<std::vector<std::string>> CandidateRetriever::retrieve(
    const TrafficGraph& graph,
    const StrategyRequest& request
) {
    const std::unordered_set<std::string> excluded = to_set(request.excluded_city_codes);
    std::vector<std::vector<std::string>> paths;
    std::vector<std::string> path{request.from_city_code};
    const int max_edges = request.max_transfers + 1;

    std::function<void(const std::string&)> dfs = [&](const std::string& current) {
        if (paths.size() >= kMaxCandidatePaths) {
            return;
        }
        if (static_cast<int>(path.size()) > max_edges + 1) {
            return;
        }
        if (current == request.to_city_code && path.size() > 1) {
            paths.push_back(path);
            return;
        }
        if (static_cast<int>(path.size()) == max_edges + 1) {
            return;
        }

        for (const auto& next_city : graph.adjacent_cities(
                 current,
                 request.allow_flight,
                 request.allow_train
             )) {
            if (excluded.count(next_city) > 0) {
                continue;
            }
            if (std::find(path.begin(), path.end(), next_city) != path.end()) {
                continue;
            }
            path.push_back(next_city);
            dfs(next_city);
            path.pop_back();
        }
    };

    dfs(request.from_city_code);
    std::sort(paths.begin(), paths.end(), [](const auto& left, const auto& right) {
        if (left.size() != right.size()) {
            return left.size() < right.size();
        }
        return left < right;
    });
    return paths;
}

double RankingModel::score(
    const StrategyRecommendation& recommendation,
    OptimizeTarget target,
    double service_score,
    double stability_score,
    double sample_score,
    bool required_transfer_satisfied,
    bool over_direct_guard,
    bool mixed_transport,
    const StrategyRankerWeights& weights
) {
    double price_weight = weights.price_weight;
    double duration_weight = weights.duration_weight;
    double transfer_weight = weights.transfer_weight;
    double service_weight = weights.service_weight;
    double confidence_weight = weights.confidence_weight;
    if (target == OptimizeTarget::Price) {
        price_weight *= 1.65;
        duration_weight *= 0.75;
    } else if (target == OptimizeTarget::Time) {
        duration_weight *= 1.65;
        price_weight *= 0.75;
    } else if (target == OptimizeTarget::Transfer) {
        transfer_weight *= 1.75;
        price_weight *= 0.75;
        duration_weight *= 0.75;
    }

    const double price_component = inverse_component(recommendation.estimated_total_price, 1000.0);
    const double duration_component =
        inverse_component(static_cast<double>(recommendation.estimated_total_duration_minutes), 600.0);
    const double transfer_component = 1.0 / (recommendation.transfer_count + 1.0);
    const double required_bonus = required_transfer_satisfied ? weights.required_transfer_bonus : 0.0;
    const double guard_penalty = over_direct_guard ? weights.direct_guard_penalty : 0.0;
    const double mix_penalty = mixed_transport ? weights.transport_mix_penalty : 0.0;

    const double score_value =
        price_component * price_weight +
        duration_component * duration_weight +
        transfer_component * transfer_weight +
        service_score * service_weight +
        recommendation.confidence * confidence_weight +
        stability_score * weights.stability_weight +
        sample_score * weights.sample_count_weight +
        required_bonus - guard_penalty - mix_penalty;
    return round_to(score_value, 4);
}

std::vector<StrategyRecommendation> RankingModel::rank(
    std::vector<StrategyRecommendation> recommendations,
    OptimizeTarget target
) {
    if (target == OptimizeTarget::Price) {
        std::sort(recommendations.begin(), recommendations.end(), [](const auto& left, const auto& right) {
            if (left.estimated_total_price != right.estimated_total_price) {
                return left.estimated_total_price < right.estimated_total_price;
            }
            if (left.confidence != right.confidence) {
                return left.confidence > right.confidence;
            }
            return left.transfer_count < right.transfer_count;
        });
        return recommendations;
    }
    if (target == OptimizeTarget::Time) {
        std::sort(recommendations.begin(), recommendations.end(), [](const auto& left, const auto& right) {
            if (left.estimated_total_duration_minutes != right.estimated_total_duration_minutes) {
                return left.estimated_total_duration_minutes < right.estimated_total_duration_minutes;
            }
            return left.estimated_total_price < right.estimated_total_price;
        });
        return recommendations;
    }
    if (target == OptimizeTarget::Transfer) {
        std::sort(recommendations.begin(), recommendations.end(), [](const auto& left, const auto& right) {
            if (left.transfer_count != right.transfer_count) {
                return left.transfer_count < right.transfer_count;
            }
            if (left.confidence != right.confidence) {
                return left.confidence > right.confidence;
            }
            return left.estimated_total_price < right.estimated_total_price;
        });
        return recommendations;
    }

    std::sort(recommendations.begin(), recommendations.end(), [](const auto& left, const auto& right) {
        if (std::abs(left.score - right.score) > 1e-9) {
            return left.score > right.score;
        }
        return left.estimated_total_price < right.estimated_total_price;
    });
    return recommendations;
}

void StrategyPlanner::load_catalog(
    const std::vector<StrategyCityInput>& cities,
    const std::vector<StrategyStationInput>& stations,
    const std::vector<StrategyRouteInput>& routes
) {
    cities_.clear();
    for (const auto& city : cities) {
        cities_[city.code] = city;
    }
    graph_ = TrafficGraphBuilder::build(stations, routes);
}

void StrategyPlanner::load_precomputed_edges(
    const std::vector<StrategyCityInput>& cities,
    const std::vector<SegmentAvailability>& edges
) {
    cities_.clear();
    for (const auto& city : cities) {
        cities_[city.code] = city;
    }
    graph_ = TrafficGraph();
    for (const auto& edge : edges) {
        graph_.add_edge(edge);
    }
}

void StrategyPlanner::set_ranker_weights(const StrategyRankerWeights& weights) {
    weights_ = weights;
}

StrategyRankerWeights StrategyPlanner::ranker_weights() const {
    return weights_;
}

std::vector<StrategyRecommendation> StrategyPlanner::recommend(const StrategyRequest& request) const {
    const auto paths = CandidateRetriever::retrieve(graph_, request);
    const double direct_price = direct_baseline(request);
    const std::unordered_set<std::string> required = to_set(request.required_transfer_city_codes);
    std::vector<StrategyRecommendation> primary;
    std::vector<StrategyRecommendation> fallback;

    for (const auto& path : paths) {
        const int transfer_count = std::max(static_cast<int>(path.size()) - 2, 0);
        if (transfer_count < request.min_transfers) {
            continue;
        }

        std::unordered_set<std::string> transfers;
        for (std::size_t index = 1; index + 1 < path.size(); ++index) {
            transfers.insert(path[index]);
        }
        const bool required_satisfied = contains_all(transfers, required);
        if (!required.empty() && !required_satisfied) {
            continue;
        }

        auto segments = build_segments(path, request);
        if (segments.size() != path.size() - 1) {
            continue;
        }

        double total_price = 0.0;
        int total_duration = 0;
        double confidence_sum = 0.0;
        double service_sum = 0.0;
        double stability_sum = 0.0;
        double sample_sum = 0.0;
        std::set<std::string> transport_types;
        std::set<std::string> data_sources;
        for (const auto& segment : segments) {
            total_price += segment.estimated_price;
            total_duration += segment.estimated_duration_minutes;
            confidence_sum += segment.availability.confidence;
            service_sum += segment.availability.service_frequency_score;
            stability_sum +=
                (segment.availability.price_stability_score + segment.availability.duration_stability_score) /
                2.0;
            sample_sum += std::min(1.0, segment.availability.sample_count / 365.0);
            transport_types.insert(transport_key(segment.recommended_transport_type));
            data_sources.insert(segment.data_source);
        }
        total_price = round_to(total_price, 2);

        if (request.max_price >= 0.0 && total_price > request.max_price) {
            continue;
        }
        if (request.max_total_duration_minutes > 0 && total_duration > request.max_total_duration_minutes) {
            continue;
        }

        const bool over_direct_guard =
            direct_price > 0.0 && transfer_count > 0 && total_price > direct_price * kPriceGuardMultiplier;

        StrategyRecommendation recommendation;
        recommendation.id = "strategy";
        for (const auto& city_code : path) {
            recommendation.id += "_" + city_code;
            const auto city_iterator = cities_.find(city_code);
            if (city_iterator == cities_.end()) {
                recommendation.city_path.push_back(city_code);
                recommendation.city_path_en.push_back(city_code);
            } else {
                recommendation.city_path.push_back(city_iterator->second.name);
                recommendation.city_path_en.push_back(city_iterator->second.name_en);
            }
        }
        for (std::size_t index = 1; index + 1 < path.size(); ++index) {
            const auto city_iterator = cities_.find(path[index]);
            recommendation.transfer_cities.push_back(
                city_iterator == cities_.end() ? path[index] : city_iterator->second.name
            );
            recommendation.transfer_cities_en.push_back(
                city_iterator == cities_.end() ? path[index] : city_iterator->second.name_en
            );
        }
        recommendation.segments = segments;
        recommendation.estimated_total_price = total_price;
        recommendation.estimated_total_duration_minutes = total_duration;
        recommendation.estimated_price_level = price_level(total_price, direct_price);
        recommendation.estimated_duration_level = duration_level(total_duration);
        recommendation.transfer_count = transfer_count;
        recommendation.confidence = round_to(confidence_sum / segments.size(), 4);
        const double service_score = service_sum / segments.size();
        const double stability_score = stability_sum / segments.size();
        const double sample_score = sample_sum / segments.size();
        recommendation.score = RankingModel::score(
            recommendation,
            request.target,
            service_score,
            stability_score,
            sample_score,
            required_satisfied,
            over_direct_guard,
            transport_types.size() > 1,
            weights_
        );
        recommendation.reasons =
            reason_codes(transfer_count, total_price, direct_price, service_score);
        recommendation.warnings = {"confirm_realtime"};
        if (over_direct_guard) {
            recommendation.warnings.push_back("above_direct_guard");
        }
        recommendation.data_sources.assign(data_sources.begin(), data_sources.end());

        if (over_direct_guard) {
            fallback.push_back(recommendation);
        } else {
            primary.push_back(recommendation);
        }
    }

    auto ranked = RankingModel::rank(primary, request.target);
    if (ranked.empty()) {
        ranked = RankingModel::rank(fallback, request.target);
    }
    if (request.max_results > 0 && ranked.size() > static_cast<std::size_t>(request.max_results)) {
        ranked.resize(static_cast<std::size_t>(request.max_results));
    }
    return ranked;
}

void StrategyPlanner::clear() {
    cities_.clear();
    graph_ = TrafficGraph();
}

std::vector<StrategySegment> StrategyPlanner::build_segments(
    const std::vector<std::string>& path,
    const StrategyRequest& request
) const {
    std::vector<StrategySegment> segments;
    for (std::size_t index = 0; index + 1 < path.size(); ++index) {
        const auto options = graph_.segment_options(
            path[index],
            path[index + 1],
            request.allow_flight,
            request.allow_train
        );
        if (options.empty()) {
            return {};
        }

        const auto& selected = options.front();
        StrategySegment segment;
        segment.from_city_code = selected.from_city_code;
        segment.to_city_code = selected.to_city_code;
        const auto from_city_iterator = cities_.find(selected.from_city_code);
        const auto to_city_iterator = cities_.find(selected.to_city_code);
        segment.from_city = from_city_iterator == cities_.end()
                                ? selected.from_city_code
                                : from_city_iterator->second.name;
        segment.to_city =
            to_city_iterator == cities_.end() ? selected.to_city_code : to_city_iterator->second.name;
        segment.from_city_en = from_city_iterator == cities_.end()
                                   ? selected.from_city_code
                                   : from_city_iterator->second.name_en;
        segment.to_city_en =
            to_city_iterator == cities_.end() ? selected.to_city_code : to_city_iterator->second.name_en;
        segment.recommended_transport_type = selected.transport_type;
        for (const auto& option : options) {
            segment.available_transport_types.push_back(option.transport_type);
        }
        segment.estimated_price = selected.estimated_price;
        segment.estimated_duration_minutes = selected.estimated_duration_minutes;
        segment.estimated_price_level = price_level(selected.estimated_price, -1.0);
        segment.estimated_duration_level = duration_level(selected.estimated_duration_minutes);
        segment.service_frequency_level = frequency_level(selected.service_frequency_score);
        segment.availability = selected;
        segment.data_source = selected.data_source;
        segments.push_back(segment);
    }
    return segments;
}

double StrategyPlanner::direct_baseline(const StrategyRequest& request) const {
    const auto options = graph_.segment_options(
        request.from_city_code,
        request.to_city_code,
        request.allow_flight,
        request.allow_train
    );
    if (options.empty()) {
        return -1.0;
    }
    return options.front().estimated_price;
}
