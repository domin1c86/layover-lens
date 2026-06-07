#pragma once

#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "planner.h"

struct StrategyCityInput {
    std::string code;
    std::string name;
    std::string name_en;
};

struct StrategyStationInput {
    std::string code;
    std::string name;
    std::string name_en;
    std::string city_code;
};

struct StrategyRouteInput {
    std::string id;
    std::string from_station;
    std::string to_station;
    TransportType transport_type;
    double price;
    int duration_minutes;
    std::string data_source;
};

struct StrategyRequest {
    std::string from_city_code;
    std::string to_city_code;
    OptimizeTarget target;
    int max_transfers;
    int min_transfers;
    int max_results;
    bool allow_flight;
    bool allow_train;
    double max_price;
    int max_total_duration_minutes;
    std::vector<std::string> excluded_city_codes;
    std::vector<std::string> required_transfer_city_codes;
};

struct SegmentAvailability {
    std::string from_city_code;
    std::string to_city_code;
    TransportType transport_type;
    int sample_count;
    double estimated_price;
    int estimated_duration_minutes;
    double service_frequency_score;
    double availability_score;
    double confidence;
    double price_stability_score;
    double duration_stability_score;
    std::string data_source;
};

struct StrategyRankerWeights {
    std::string version = "builtin_default";
    double price_weight = 0.35;
    double duration_weight = 0.25;
    double transfer_weight = 0.20;
    double service_weight = 0.15;
    double confidence_weight = 0.10;
    double stability_weight = 0.08;
    double sample_count_weight = 0.03;
    double required_transfer_bonus = 0.08;
    double direct_guard_penalty = 0.40;
    double transport_mix_penalty = 0.03;
};

struct StrategySegment {
    std::string from_city_code;
    std::string to_city_code;
    std::string from_city;
    std::string to_city;
    std::string from_city_en;
    std::string to_city_en;
    TransportType recommended_transport_type;
    std::vector<TransportType> available_transport_types;
    double estimated_price;
    int estimated_duration_minutes;
    std::string estimated_price_level;
    std::string estimated_duration_level;
    std::string service_frequency_level;
    SegmentAvailability availability;
    std::string data_source;
};

struct StrategyRecommendation {
    std::string id;
    std::vector<std::string> city_path;
    std::vector<std::string> city_path_en;
    std::vector<std::string> transfer_cities;
    std::vector<std::string> transfer_cities_en;
    std::vector<StrategySegment> segments;
    double estimated_total_price;
    int estimated_total_duration_minutes;
    std::string estimated_price_level;
    std::string estimated_duration_level;
    int transfer_count;
    double score;
    double confidence;
    std::vector<std::string> reasons;
    std::vector<std::string> warnings;
    std::vector<std::string> data_sources;
};

class TrafficGraph {
public:
    void add_edge(const SegmentAvailability& edge);
    std::vector<std::string> adjacent_cities(
        const std::string& city_code,
        bool allow_flight,
        bool allow_train
    ) const;
    std::vector<SegmentAvailability> segment_options(
        const std::string& from_city_code,
        const std::string& to_city_code,
        bool allow_flight,
        bool allow_train
    ) const;

private:
    std::unordered_map<std::string, std::vector<SegmentAvailability>> segments_by_pair_;
    std::unordered_map<std::string, std::vector<std::string>> adjacency_;
};

class TrafficGraphBuilder {
public:
    static TrafficGraph build(
        const std::vector<StrategyStationInput>& stations,
        const std::vector<StrategyRouteInput>& routes
    );
};

class CandidateRetriever {
public:
    static std::vector<std::vector<std::string>> retrieve(
        const TrafficGraph& graph,
        const StrategyRequest& request
    );
};

class RankingModel {
public:
    static double score(
        const StrategyRecommendation& recommendation,
        OptimizeTarget target,
        double service_score,
        double stability_score,
        double sample_score,
        bool required_transfer_satisfied,
        bool over_direct_guard,
        bool mixed_transport,
        const StrategyRankerWeights& weights
    );
    static std::vector<StrategyRecommendation> rank(
        std::vector<StrategyRecommendation> recommendations,
        OptimizeTarget target
    );
};

class StrategyPlanner {
public:
    void load_catalog(
        const std::vector<StrategyCityInput>& cities,
        const std::vector<StrategyStationInput>& stations,
        const std::vector<StrategyRouteInput>& routes
    );
    void load_precomputed_edges(
        const std::vector<StrategyCityInput>& cities,
        const std::vector<SegmentAvailability>& edges
    );
    void set_ranker_weights(const StrategyRankerWeights& weights);
    StrategyRankerWeights ranker_weights() const;
    std::vector<StrategyRecommendation> recommend(const StrategyRequest& request) const;
    void clear();

private:
    TrafficGraph graph_;
    std::unordered_map<std::string, StrategyCityInput> cities_;
    StrategyRankerWeights weights_;

    std::vector<StrategySegment> build_segments(
        const std::vector<std::string>& path,
        const StrategyRequest& request
    ) const;
    double direct_baseline(const StrategyRequest& request) const;
};
