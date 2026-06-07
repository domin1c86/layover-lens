#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "planner.h"
#include "strategy_planner.h"

namespace py = pybind11;

PYBIND11_MODULE(route_planner, m) {
    m.doc() = "Layover Lens route planner";

    py::enum_<TransportType>(m, "TransportType")
        .value("FLIGHT", TransportType::Flight)
        .value("TRAIN", TransportType::Train);

    py::enum_<OptimizeTarget>(m, "OptimizeTarget")
        .value("PRICE", OptimizeTarget::Price)
        .value("TIME", OptimizeTarget::Time)
        .value("TRANSFER", OptimizeTarget::Transfer)
        .value("BALANCED", OptimizeTarget::Balanced);

    py::class_<Edge>(m, "Edge")
        .def_readonly("route_id", &Edge::route_id)
        .def_readonly("from_node", &Edge::from_node)
        .def_readonly("to_node", &Edge::to_node)
        .def_readonly("from_city", &Edge::from_city)
        .def_readonly("to_city", &Edge::to_city)
        .def_readonly("from_station", &Edge::from_station)
        .def_readonly("to_station", &Edge::to_station)
        .def_readonly("transport_type", &Edge::transport_type)
        .def_readonly("departure_date", &Edge::departure_date)
        .def_readonly("departure_time", &Edge::departure_time)
        .def_readonly("arrival_date", &Edge::arrival_date)
        .def_readonly("arrival_time", &Edge::arrival_time)
        .def_readonly("duration_minutes", &Edge::duration_minutes)
        .def_readonly("price", &Edge::price)
        .def_readonly("company", &Edge::company)
        .def_readonly("flight_train_no", &Edge::flight_train_no);

    py::class_<RoutePlan>(m, "RoutePlan")
        .def_readonly("legs", &RoutePlan::legs)
        .def_readonly("total_duration_minutes", &RoutePlan::total_duration_minutes)
        .def_readonly("total_price", &RoutePlan::total_price)
        .def_readonly("transfer_count", &RoutePlan::transfer_count)
        .def_readonly("score", &RoutePlan::score);

    py::class_<StrategyCityInput>(m, "StrategyCityInput")
        .def(py::init<>())
        .def_readwrite("code", &StrategyCityInput::code)
        .def_readwrite("name", &StrategyCityInput::name)
        .def_readwrite("name_en", &StrategyCityInput::name_en);

    py::class_<StrategyStationInput>(m, "StrategyStationInput")
        .def(py::init<>())
        .def_readwrite("code", &StrategyStationInput::code)
        .def_readwrite("name", &StrategyStationInput::name)
        .def_readwrite("name_en", &StrategyStationInput::name_en)
        .def_readwrite("city_code", &StrategyStationInput::city_code);

    py::class_<StrategyRouteInput>(m, "StrategyRouteInput")
        .def(py::init<>())
        .def_readwrite("id", &StrategyRouteInput::id)
        .def_readwrite("from_station", &StrategyRouteInput::from_station)
        .def_readwrite("to_station", &StrategyRouteInput::to_station)
        .def_readwrite("transport_type", &StrategyRouteInput::transport_type)
        .def_readwrite("price", &StrategyRouteInput::price)
        .def_readwrite("duration_minutes", &StrategyRouteInput::duration_minutes)
        .def_readwrite("data_source", &StrategyRouteInput::data_source);

    py::class_<StrategyRequest>(m, "StrategyRequest")
        .def(py::init<>())
        .def_readwrite("from_city_code", &StrategyRequest::from_city_code)
        .def_readwrite("to_city_code", &StrategyRequest::to_city_code)
        .def_readwrite("target", &StrategyRequest::target)
        .def_readwrite("max_transfers", &StrategyRequest::max_transfers)
        .def_readwrite("min_transfers", &StrategyRequest::min_transfers)
        .def_readwrite("max_results", &StrategyRequest::max_results)
        .def_readwrite("allow_flight", &StrategyRequest::allow_flight)
        .def_readwrite("allow_train", &StrategyRequest::allow_train)
        .def_readwrite("max_price", &StrategyRequest::max_price)
        .def_readwrite("max_total_duration_minutes", &StrategyRequest::max_total_duration_minutes)
        .def_readwrite("excluded_city_codes", &StrategyRequest::excluded_city_codes)
        .def_readwrite("required_transfer_city_codes", &StrategyRequest::required_transfer_city_codes);

    py::class_<SegmentAvailability>(m, "SegmentAvailability")
        .def(py::init<>())
        .def_readwrite("from_city_code", &SegmentAvailability::from_city_code)
        .def_readwrite("to_city_code", &SegmentAvailability::to_city_code)
        .def_readwrite("transport_type", &SegmentAvailability::transport_type)
        .def_readwrite("sample_count", &SegmentAvailability::sample_count)
        .def_readwrite("estimated_price", &SegmentAvailability::estimated_price)
        .def_readwrite("estimated_duration_minutes", &SegmentAvailability::estimated_duration_minutes)
        .def_readwrite("service_frequency_score", &SegmentAvailability::service_frequency_score)
        .def_readwrite("availability_score", &SegmentAvailability::availability_score)
        .def_readwrite("confidence", &SegmentAvailability::confidence)
        .def_readwrite("price_stability_score", &SegmentAvailability::price_stability_score)
        .def_readwrite("duration_stability_score", &SegmentAvailability::duration_stability_score)
        .def_readwrite("data_source", &SegmentAvailability::data_source);

    py::class_<StrategyRankerWeights>(m, "StrategyRankerWeights")
        .def(py::init<>())
        .def_readwrite("version", &StrategyRankerWeights::version)
        .def_readwrite("price_weight", &StrategyRankerWeights::price_weight)
        .def_readwrite("duration_weight", &StrategyRankerWeights::duration_weight)
        .def_readwrite("transfer_weight", &StrategyRankerWeights::transfer_weight)
        .def_readwrite("service_weight", &StrategyRankerWeights::service_weight)
        .def_readwrite("confidence_weight", &StrategyRankerWeights::confidence_weight)
        .def_readwrite("stability_weight", &StrategyRankerWeights::stability_weight)
        .def_readwrite("sample_count_weight", &StrategyRankerWeights::sample_count_weight)
        .def_readwrite("required_transfer_bonus", &StrategyRankerWeights::required_transfer_bonus)
        .def_readwrite("direct_guard_penalty", &StrategyRankerWeights::direct_guard_penalty)
        .def_readwrite("transport_mix_penalty", &StrategyRankerWeights::transport_mix_penalty);

    py::class_<StrategySegment>(m, "StrategySegment")
        .def_readonly("from_city_code", &StrategySegment::from_city_code)
        .def_readonly("to_city_code", &StrategySegment::to_city_code)
        .def_readonly("from_city", &StrategySegment::from_city)
        .def_readonly("to_city", &StrategySegment::to_city)
        .def_readonly("from_city_en", &StrategySegment::from_city_en)
        .def_readonly("to_city_en", &StrategySegment::to_city_en)
        .def_readonly("recommended_transport_type", &StrategySegment::recommended_transport_type)
        .def_readonly("available_transport_types", &StrategySegment::available_transport_types)
        .def_readonly("estimated_price", &StrategySegment::estimated_price)
        .def_readonly("estimated_duration_minutes", &StrategySegment::estimated_duration_minutes)
        .def_readonly("estimated_price_level", &StrategySegment::estimated_price_level)
        .def_readonly("estimated_duration_level", &StrategySegment::estimated_duration_level)
        .def_readonly("service_frequency_level", &StrategySegment::service_frequency_level)
        .def_readonly("availability", &StrategySegment::availability)
        .def_readonly("data_source", &StrategySegment::data_source);

    py::class_<StrategyRecommendation>(m, "StrategyRecommendation")
        .def_readonly("id", &StrategyRecommendation::id)
        .def_readonly("city_path", &StrategyRecommendation::city_path)
        .def_readonly("city_path_en", &StrategyRecommendation::city_path_en)
        .def_readonly("transfer_cities", &StrategyRecommendation::transfer_cities)
        .def_readonly("transfer_cities_en", &StrategyRecommendation::transfer_cities_en)
        .def_readonly("segments", &StrategyRecommendation::segments)
        .def_readonly("estimated_total_price", &StrategyRecommendation::estimated_total_price)
        .def_readonly("estimated_total_duration_minutes", &StrategyRecommendation::estimated_total_duration_minutes)
        .def_readonly("estimated_price_level", &StrategyRecommendation::estimated_price_level)
        .def_readonly("estimated_duration_level", &StrategyRecommendation::estimated_duration_level)
        .def_readonly("transfer_count", &StrategyRecommendation::transfer_count)
        .def_readonly("score", &StrategyRecommendation::score)
        .def_readonly("confidence", &StrategyRecommendation::confidence)
        .def_readonly("reasons", &StrategyRecommendation::reasons)
        .def_readonly("warnings", &StrategyRecommendation::warnings)
        .def_readonly("data_sources", &StrategyRecommendation::data_sources);

    py::class_<PathPlanner>(m, "PathPlanner")
        .def(py::init<>())
        .def("add_node", &PathPlanner::add_node)
        .def(
            "add_edge",
            &PathPlanner::add_edge,
            py::arg("from_node"),
            py::arg("to_node"),
            py::arg("transport_type"),
            py::arg("route_id"),
            py::arg("from_city"),
            py::arg("to_city"),
            py::arg("from_station"),
            py::arg("to_station"),
            py::arg("departure_date"),
            py::arg("departure_time"),
            py::arg("arrival_date"),
            py::arg("arrival_time"),
            py::arg("duration_minutes"),
            py::arg("price"),
            py::arg("company"),
            py::arg("flight_train_no")
        )
        .def(
            "find_routes",
            &PathPlanner::find_routes,
            py::arg("from_node"),
            py::arg("to_node"),
            py::arg("travel_date"),
            py::arg("target"),
            py::arg("max_transfers"),
            py::arg("max_results"),
            py::arg("min_transfer_minutes_same_station"),
            py::arg("min_transfer_minutes_same_city"),
            py::arg("max_layover_minutes"),
            py::arg("max_total_duration_minutes"),
            py::arg("allow_flight"),
            py::arg("allow_train"),
            py::arg("max_price"),
            py::arg("excluded_nodes"),
            py::arg("required_transfer_nodes"),
            py::arg("departure_time_start_minutes"),
            py::arg("departure_time_end_minutes"),
            py::arg("arrival_time_start_minutes"),
            py::arg("arrival_time_end_minutes"),
            py::arg("allow_overnight")
        )
        .def("clear_graph", &PathPlanner::clear_graph);

    py::class_<StrategyPlanner>(m, "StrategyPlanner")
        .def(py::init<>())
        .def("load_catalog", &StrategyPlanner::load_catalog)
        .def("load_precomputed_edges", &StrategyPlanner::load_precomputed_edges)
        .def("set_ranker_weights", &StrategyPlanner::set_ranker_weights)
        .def("ranker_weights", &StrategyPlanner::ranker_weights)
        .def("recommend", &StrategyPlanner::recommend)
        .def("clear", &StrategyPlanner::clear);
}
