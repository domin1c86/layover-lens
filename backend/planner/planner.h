#pragma once

#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

enum class TransportType { Flight, Train };
enum class OptimizeTarget { Price, Time, Transfer, Balanced };

struct Edge {
    std::string from_node;
    std::string to_node;
    TransportType transport_type;
    int duration_minutes;
    double price;
    std::string schedule_id;
};

struct RoutePlan {
    std::vector<Edge> legs;
    int total_duration_minutes;
    double total_price;
    int transfer_count;
    double score;
};

class PathPlanner {
public:
    void add_node(const std::string& node_id);
    void add_edge(
        const std::string& from_node,
        const std::string& to_node,
        TransportType transport_type,
        int duration_minutes,
        double price,
        const std::string& schedule_id
    );
    std::vector<RoutePlan> find_routes(
        const std::string& from_node,
        const std::string& to_node,
        OptimizeTarget target,
        int max_transfers,
        int max_results
    ) const;
    void clear_graph();

private:
    std::unordered_map<std::string, std::vector<Edge>> adjacency_;
    void depth_first_search(
        const std::string& current_node,
        const std::string& target_node,
        OptimizeTarget target,
        int max_transfers,
        std::vector<Edge>& current_legs,
        std::vector<RoutePlan>& results,
        std::unordered_map<std::string, bool>& visited
    ) const;
    static double compute_score(const RoutePlan& route, OptimizeTarget target);
};
