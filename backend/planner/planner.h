#pragma once

#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

enum class TransportType { Flight, Train };
enum class OptimizeTarget { Price, Time, Transfer, Balanced };

struct Edge {
    std::string route_id;
    std::string from_node;
    std::string to_node;
    std::string from_city;
    std::string to_city;
    std::string from_station;
    std::string to_station;
    TransportType transport_type;
    std::string departure_date;
    std::string departure_time;
    std::string arrival_date;
    std::string arrival_time;
    long long departure_at_minutes;
    long long arrival_at_minutes;
    int duration_minutes;
    double price;
    std::string company;
    std::string flight_train_no;
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
    );
    std::vector<RoutePlan> find_routes(
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
    ) const;
    void clear_graph();

private:
    std::unordered_map<std::string, std::vector<Edge>> adjacency_;

    static long long parse_datetime_minutes(
        const std::string& date_text,
        const std::string& time_text
    );
    static int transfer_buffer_minutes(
        const std::string& previous_station,
        const std::string& next_station,
        int same_station_minutes,
        int same_city_minutes
    );
    static std::vector<RoutePlan> dedupe_routes(const std::vector<RoutePlan>& routes);
    static std::vector<RoutePlan> rank_routes(
        const std::vector<RoutePlan>& routes,
        OptimizeTarget target
    );
    static std::vector<RoutePlan> rank_balanced(const std::vector<RoutePlan>& routes);
    static int time_of_day_minutes(long long absolute_minutes);
    static bool in_time_window(int value, int start_minutes, int end_minutes);
    static bool route_has_overnight(const RoutePlan& route);
    static double compute_score(const RoutePlan& route, OptimizeTarget target);
};
