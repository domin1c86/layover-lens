#include "planner.h"

#include <algorithm>

void PathPlanner::add_node(const std::string& node_id) {
    adjacency_.try_emplace(node_id, std::vector<Edge>{});
}

void PathPlanner::add_edge(
    const std::string& from_node,
    const std::string& to_node,
    TransportType transport_type,
    int duration_minutes,
    double price,
    const std::string& schedule_id
) {
    add_node(from_node);
    add_node(to_node);
    adjacency_[from_node].push_back(
        Edge{from_node, to_node, transport_type, duration_minutes, price, schedule_id}
    );
}

std::vector<RoutePlan> PathPlanner::find_routes(
    const std::string& from_node,
    const std::string& to_node,
    OptimizeTarget target,
    int max_transfers,
    int max_results
) const {
    std::vector<RoutePlan> results;
    std::vector<Edge> current_legs;
    std::unordered_map<std::string, bool> visited;
    depth_first_search(
        from_node,
        to_node,
        target,
        max_transfers,
        current_legs,
        results,
        visited
    );

    std::sort(
        results.begin(),
        results.end(),
        [](const RoutePlan& left, const RoutePlan& right) { return left.score > right.score; }
    );

    if (results.size() > static_cast<std::size_t>(max_results)) {
        results.resize(static_cast<std::size_t>(max_results));
    }

    return results;
}

void PathPlanner::clear_graph() {
    adjacency_.clear();
}

void PathPlanner::depth_first_search(
    const std::string& current_node,
    const std::string& target_node,
    OptimizeTarget target,
    int max_transfers,
    std::vector<Edge>& current_legs,
    std::vector<RoutePlan>& results,
    std::unordered_map<std::string, bool>& visited
) const {
    if (current_node == target_node && !current_legs.empty()) {
        int total_duration = 0;
        double total_price = 0.0;
        for (const auto& edge : current_legs) {
            total_duration += edge.duration_minutes;
            total_price += edge.price;
        }

        RoutePlan route{
            current_legs,
            total_duration,
            total_price,
            static_cast<int>(current_legs.size()) - 1,
            0.0,
        };
        route.score = compute_score(route, target);
        results.push_back(route);
        return;
    }

    if (static_cast<int>(current_legs.size()) > max_transfers) {
        return;
    }

    visited[current_node] = true;
    const auto iterator = adjacency_.find(current_node);
    if (iterator == adjacency_.end()) {
        visited[current_node] = false;
        return;
    }

    for (const auto& edge : iterator->second) {
        if (visited[edge.to_node]) {
            continue;
        }

        current_legs.push_back(edge);
        depth_first_search(
            edge.to_node,
            target_node,
            target,
            max_transfers,
            current_legs,
            results,
            visited
        );
        current_legs.pop_back();
    }

    visited[current_node] = false;
}

double PathPlanner::compute_score(const RoutePlan& route, OptimizeTarget target) {
    switch (target) {
        case OptimizeTarget::Price:
            return 100000.0 / (route.total_price + 1.0);
        case OptimizeTarget::Time:
            return 100000.0 / (route.total_duration_minutes + 1.0);
        case OptimizeTarget::Transfer:
            return 10000.0 / (route.transfer_count + 1.0) -
                   static_cast<double>(route.total_duration_minutes) * 0.01;
        case OptimizeTarget::Balanced:
        default:
            return 50.0 / (route.total_price + 1.0) +
                   40.0 / (route.total_duration_minutes + 1.0) +
                   10.0 / (route.transfer_count + 1.0);
    }
}
