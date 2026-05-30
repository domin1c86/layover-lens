#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "planner.h"

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
}
