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
        .def_readonly("from_node", &Edge::from_node)
        .def_readonly("to_node", &Edge::to_node)
        .def_readonly("transport_type", &Edge::transport_type)
        .def_readonly("duration_minutes", &Edge::duration_minutes)
        .def_readonly("price", &Edge::price)
        .def_readonly("schedule_id", &Edge::schedule_id);

    py::class_<RoutePlan>(m, "RoutePlan")
        .def_readonly("legs", &RoutePlan::legs)
        .def_readonly("total_duration_minutes", &RoutePlan::total_duration_minutes)
        .def_readonly("total_price", &RoutePlan::total_price)
        .def_readonly("transfer_count", &RoutePlan::transfer_count)
        .def_readonly("score", &RoutePlan::score);

    py::class_<PathPlanner>(m, "PathPlanner")
        .def(py::init<>())
        .def("add_node", &PathPlanner::add_node)
        .def("add_edge", &PathPlanner::add_edge)
        .def("find_routes", &PathPlanner::find_routes)
        .def("clear_graph", &PathPlanner::clear_graph);
}
