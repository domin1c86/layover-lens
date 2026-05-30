#include "planner.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <sstream>

namespace {

long long days_from_civil(int year, unsigned month, unsigned day) {
    year -= month <= 2 ? 1 : 0;
    const int era = (year >= 0 ? year : year - 399) / 400;
    const unsigned yoe = static_cast<unsigned>(year - era * 400);
    const unsigned doy =
        (153 * (month + (month > 2 ? static_cast<unsigned>(-3) : 9)) + 2) / 5 + day - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return static_cast<long long>(era) * 146097 + static_cast<long long>(doe) - 719468;
}

double round_to(double value, int digits) {
    const double factor = std::pow(10.0, digits);
    return std::round(value * factor) / factor;
}

std::string route_signature(const RoutePlan& route) {
    std::ostringstream signature;
    for (const auto& leg : route.legs) {
        signature << leg.route_id << '@' << leg.departure_at_minutes << '-' << leg.arrival_at_minutes
                  << '|';
    }
    return signature.str();
}

double normalize(double value, double min_value, double max_value) {
    if (std::abs(max_value - min_value) < 1e-9) {
        return 1.0;
    }

    return 1.0 - ((value - min_value) / (max_value - min_value));
}

}  // namespace

void PathPlanner::add_node(const std::string& node_id) {
    adjacency_.try_emplace(node_id, std::vector<Edge>{});
}

void PathPlanner::add_edge(
    const std::string& from_node,
    const std::string& to_node,
    TransportType transport_type,
    const std::string& route_id,
    const std::string& from_city,
    const std::string& to_city,
    const std::string& from_station,
    const std::string& to_station,
    const std::string& departure_date,
    const std::string& departure_time,
    const std::string& arrival_date,
    const std::string& arrival_time,
    int duration_minutes,
    double price,
    const std::string& company,
    const std::string& flight_train_no
) {
    add_node(from_node);
    add_node(to_node);
    adjacency_[from_node].push_back(Edge{
        route_id,
        from_node,
        to_node,
        from_city,
        to_city,
        from_station,
        to_station,
        transport_type,
        departure_date,
        departure_time,
        arrival_date,
        arrival_time,
        parse_datetime_minutes(departure_date, departure_time),
        parse_datetime_minutes(arrival_date, arrival_time),
        duration_minutes,
        price,
        company,
        flight_train_no,
    });
}

std::vector<RoutePlan> PathPlanner::find_routes(
    const std::string& from_node,
    const std::string& to_node,
    const std::string& travel_date,
    OptimizeTarget target,
    int max_transfers,
    int max_results,
    int min_transfer_minutes_same_station,
    int min_transfer_minutes_same_city,
    int max_layover_minutes,
    int max_total_duration_minutes,
    bool allow_flight,
    bool allow_train,
    double max_price,
    const std::vector<std::string>& excluded_nodes,
    const std::vector<std::string>& required_transfer_nodes,
    int departure_time_start_minutes,
    int departure_time_end_minutes,
    int arrival_time_start_minutes,
    int arrival_time_end_minutes,
    bool allow_overnight
) const {
    std::unordered_map<std::string, std::vector<Edge>> sorted_adjacency = adjacency_;
    for (auto& entry : sorted_adjacency) {
        std::sort(
            entry.second.begin(),
            entry.second.end(),
            [](const Edge& left, const Edge& right) {
                if (left.departure_at_minutes != right.departure_at_minutes) {
                    return left.departure_at_minutes < right.departure_at_minutes;
                }
                if (left.arrival_at_minutes != right.arrival_at_minutes) {
                    return left.arrival_at_minutes < right.arrival_at_minutes;
                }
                return left.route_id < right.route_id;
            }
        );
    }

    std::vector<RoutePlan> results;
    std::vector<Edge> current_legs;
    std::unordered_set<std::string> visited_nodes{from_node};
    const std::unordered_set<std::string> excluded_node_set(
        excluded_nodes.begin(),
        excluded_nodes.end()
    );
    const std::unordered_set<std::string> required_transfer_node_set(
        required_transfer_nodes.begin(),
        required_transfer_nodes.end()
    );
    const int max_legs = max_transfers + 1;

    std::function<void(
        const std::string&,
        long long,
        const std::string&,
        long long,
        double
    )>
        dfs = [&](const std::string& current_node,
                  long long previous_arrival_minutes,
                  const std::string& previous_station,
                  long long first_departure_minutes,
                  double total_price) {
            if (!current_legs.empty() && current_node == to_node) {
                RoutePlan candidate{
                    current_legs,
                    static_cast<int>(current_legs.back().arrival_at_minutes - first_departure_minutes),
                    round_to(total_price, 2),
                    static_cast<int>(current_legs.size()) - 1,
                    0.0,
                };

                if (max_price >= 0.0 && candidate.total_price > max_price) {
                    return;
                }

                if (departure_time_start_minutes >= 0 &&
                    !in_time_window(
                        time_of_day_minutes(candidate.legs.front().departure_at_minutes),
                        departure_time_start_minutes,
                        departure_time_end_minutes
                    )) {
                    return;
                }

                if (arrival_time_start_minutes >= 0 &&
                    !in_time_window(
                        time_of_day_minutes(candidate.legs.back().arrival_at_minutes),
                        arrival_time_start_minutes,
                        arrival_time_end_minutes
                    )) {
                    return;
                }

                if (!allow_overnight && route_has_overnight(candidate)) {
                    return;
                }

                if (!required_transfer_node_set.empty()) {
                    std::unordered_set<std::string> transfer_nodes;
                    for (std::size_t index = 0; index + 1 < candidate.legs.size(); ++index) {
                        transfer_nodes.insert(candidate.legs[index].to_node);
                    }
                    for (const auto& node : required_transfer_node_set) {
                        if (transfer_nodes.count(node) == 0) {
                            return;
                        }
                    }
                }

                results.push_back(candidate);
                return;
            }

            if (static_cast<int>(current_legs.size()) >= max_legs) {
                return;
            }

            const auto iterator = sorted_adjacency.find(current_node);
            if (iterator == sorted_adjacency.end()) {
                return;
            }

            for (const auto& edge : iterator->second) {
                if (
                    (edge.transport_type == TransportType::Flight && !allow_flight) ||
                    (edge.transport_type == TransportType::Train && !allow_train)
                ) {
                    continue;
                }

                if (current_legs.empty()) {
                    if (edge.departure_date != travel_date) {
                        continue;
                    }
                    if (
                        departure_time_start_minutes >= 0 &&
                        !in_time_window(
                            time_of_day_minutes(edge.departure_at_minutes),
                            departure_time_start_minutes,
                            departure_time_end_minutes
                        )
                    ) {
                        continue;
                    }
                } else {
                    const int transfer_buffer = transfer_buffer_minutes(
                        previous_station,
                        edge.from_station,
                        min_transfer_minutes_same_station,
                        min_transfer_minutes_same_city
                    );
                    const long long earliest_departure =
                        previous_arrival_minutes + static_cast<long long>(transfer_buffer);
                    if (edge.departure_at_minutes < earliest_departure) {
                        continue;
                    }
                    if (edge.departure_at_minutes - previous_arrival_minutes > max_layover_minutes) {
                        continue;
                    }
                }

                const long long effective_departure =
                    current_legs.empty() ? edge.departure_at_minutes : first_departure_minutes;
                if (edge.arrival_at_minutes - effective_departure > max_total_duration_minutes) {
                    continue;
                }

                const double projected_price = total_price + edge.price;
                if (max_price >= 0.0 && projected_price > max_price) {
                    continue;
                }

                if (edge.to_node != to_node && visited_nodes.count(edge.to_node) > 0) {
                    continue;
                }

                if (excluded_node_set.count(edge.to_node) > 0) {
                    continue;
                }

                current_legs.push_back(edge);
                const bool inserted = visited_nodes.insert(edge.to_node).second;
                dfs(
                    edge.to_node,
                    edge.arrival_at_minutes,
                    edge.to_station,
                    effective_departure,
                    projected_price
                );
                if (inserted) {
                    visited_nodes.erase(edge.to_node);
                }
                current_legs.pop_back();
            }
        };

    dfs(from_node, 0, "", 0, 0.0);

    const auto deduped = dedupe_routes(results);
    auto ranked = rank_routes(deduped, target);
    if (ranked.size() > static_cast<std::size_t>(max_results)) {
        ranked.resize(static_cast<std::size_t>(max_results));
    }

    return ranked;
}

void PathPlanner::clear_graph() {
    adjacency_.clear();
}

long long PathPlanner::parse_datetime_minutes(
    const std::string& date_text,
    const std::string& time_text
) {
    int year = 0;
    int month = 0;
    int day = 0;
    int hour = 0;
    int minute = 0;

    char separator = '-';
    std::istringstream date_stream(date_text);
    date_stream >> year >> separator >> month >> separator >> day;

    separator = ':';
    std::istringstream time_stream(time_text);
    time_stream >> hour >> separator >> minute;

    return days_from_civil(year, static_cast<unsigned>(month), static_cast<unsigned>(day)) * 1440LL +
           static_cast<long long>(hour * 60 + minute);
}

int PathPlanner::transfer_buffer_minutes(
    const std::string& previous_station,
    const std::string& next_station,
    int same_station_minutes,
    int same_city_minutes
) {
    if (previous_station.empty()) {
        return 0;
    }
    if (previous_station == next_station) {
        return same_station_minutes;
    }
    return same_city_minutes;
}

std::vector<RoutePlan> PathPlanner::dedupe_routes(const std::vector<RoutePlan>& routes) {
    std::vector<RoutePlan> deduped;
    std::unordered_set<std::string> seen;

    for (const auto& route : routes) {
        const auto signature = route_signature(route);
        if (seen.count(signature) > 0) {
            continue;
        }
        seen.insert(signature);
        deduped.push_back(route);
    }

    return deduped;
}

std::vector<RoutePlan> PathPlanner::rank_routes(
    const std::vector<RoutePlan>& routes,
    OptimizeTarget target
) {
    if (routes.empty()) {
        return {};
    }

    std::vector<RoutePlan> ranked = routes;
    if (target == OptimizeTarget::Balanced) {
        return rank_balanced(ranked);
    }

    std::sort(
        ranked.begin(),
        ranked.end(),
        [target](const RoutePlan& left, const RoutePlan& right) {
            if (target == OptimizeTarget::Price) {
                if (left.total_price != right.total_price) {
                    return left.total_price < right.total_price;
                }
                if (left.total_duration_minutes != right.total_duration_minutes) {
                    return left.total_duration_minutes < right.total_duration_minutes;
                }
                return left.transfer_count < right.transfer_count;
            }

            if (target == OptimizeTarget::Time) {
                if (left.total_duration_minutes != right.total_duration_minutes) {
                    return left.total_duration_minutes < right.total_duration_minutes;
                }
                if (left.total_price != right.total_price) {
                    return left.total_price < right.total_price;
                }
                return left.transfer_count < right.transfer_count;
            }

            if (left.transfer_count != right.transfer_count) {
                return left.transfer_count < right.transfer_count;
            }
            if (left.total_duration_minutes != right.total_duration_minutes) {
                return left.total_duration_minutes < right.total_duration_minutes;
            }
            return left.total_price < right.total_price;
        }
    );

    for (auto& route : ranked) {
        route.score = 0.0;
    }

    return ranked;
}

std::vector<RoutePlan> PathPlanner::rank_balanced(const std::vector<RoutePlan>& routes) {
    double min_price = std::numeric_limits<double>::max();
    double max_price = std::numeric_limits<double>::lowest();
    double min_duration = std::numeric_limits<double>::max();
    double max_duration = std::numeric_limits<double>::lowest();
    double min_transfer = std::numeric_limits<double>::max();
    double max_transfer = std::numeric_limits<double>::lowest();

    for (const auto& route : routes) {
        min_price = std::min(min_price, route.total_price);
        max_price = std::max(max_price, route.total_price);
        min_duration = std::min(min_duration, static_cast<double>(route.total_duration_minutes));
        max_duration = std::max(max_duration, static_cast<double>(route.total_duration_minutes));
        min_transfer = std::min(min_transfer, static_cast<double>(route.transfer_count));
        max_transfer = std::max(max_transfer, static_cast<double>(route.transfer_count));
    }

    std::vector<RoutePlan> scored = routes;
    for (auto& route : scored) {
        route.score = round_to(
            normalize(route.total_price, min_price, max_price) * 0.4 +
                normalize(
                    static_cast<double>(route.total_duration_minutes),
                    min_duration,
                    max_duration
                ) *
                    0.35 +
                normalize(
                    static_cast<double>(route.transfer_count),
                    min_transfer,
                    max_transfer
                ) *
                    0.25,
            4
        );
    }

    std::sort(
        scored.begin(),
        scored.end(),
        [](const RoutePlan& left, const RoutePlan& right) {
            if (std::abs(left.score - right.score) > 1e-9) {
                return left.score > right.score;
            }
            if (left.total_price != right.total_price) {
                return left.total_price < right.total_price;
            }
            return left.total_duration_minutes < right.total_duration_minutes;
        }
    );

    return scored;
}

int PathPlanner::time_of_day_minutes(long long absolute_minutes) {
    long long normalized = absolute_minutes % 1440LL;
    if (normalized < 0) {
        normalized += 1440LL;
    }
    return static_cast<int>(normalized);
}

bool PathPlanner::in_time_window(int value, int start_minutes, int end_minutes) {
    if (start_minutes < 0 || end_minutes < 0) {
        return true;
    }
    if (start_minutes <= end_minutes) {
        return value >= start_minutes && value <= end_minutes;
    }
    return value >= start_minutes || value <= end_minutes;
}

bool PathPlanner::route_has_overnight(const RoutePlan& route) {
    if (route.legs.empty()) {
        return false;
    }

    const long long departure_day = route.legs.front().departure_at_minutes / 1440LL;
    const long long arrival_day = route.legs.back().arrival_at_minutes / 1440LL;
    if (departure_day != arrival_day) {
        return true;
    }

    for (const auto& leg : route.legs) {
        if (leg.departure_at_minutes / 1440LL != leg.arrival_at_minutes / 1440LL) {
            return true;
        }
    }

    return false;
}

double PathPlanner::compute_score(const RoutePlan& route, OptimizeTarget target) {
    if (target == OptimizeTarget::Balanced) {
        return route.score;
    }

    switch (target) {
        case OptimizeTarget::Price:
            return route.total_price;
        case OptimizeTarget::Time:
            return static_cast<double>(route.total_duration_minutes);
        case OptimizeTarget::Transfer:
            return static_cast<double>(route.transfer_count);
        case OptimizeTarget::Balanced:
        default:
            return route.score;
    }
}
