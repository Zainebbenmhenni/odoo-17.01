/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class BookingDashboard extends Component {
    // Définition explicite des props
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        className: { type: String, optional: true }
    };

    static template = "travel_booking.BookingDashboard";

    setup() {
        console.log("BookingDashboard setup");
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            bookingsData: {
                total: 0,
                confirmed: 0,
                pending: 0,
                cancelled: 0,
                recentBookings: [],
                genderData: [],
                airlineData: []
            }
        });

        console.log("Before loadDashboardData");
        this.loadDashboardData();
    }

    async loadDashboardData() {
        try {
            // Appel sécurisé à la méthode Python
            const dashboardData = await this.orm.call(
                "booking",
                "get_dashboard_data",
                [], // Passer un tableau vide si aucun paramètre n'est nécessaire
                {}
            );

            // Transformation des données pour le state
            this.state.bookingsData = {
                total: dashboardData.total || 0,
                confirmed: dashboardData.confirmed || 0,
                pending: dashboardData.pending || 0,
                cancelled: dashboardData.cancelled || 0,
                recentBookings: dashboardData.recent_bookings || [],
                genderData: dashboardData.gender_distribution || [],
                airlineData: dashboardData.airline_distribution || []
            };

            // Attendre que le DOM soit mis à jour avant de rendre les graphiques
            await new Promise(resolve => setTimeout(resolve, 50));
            this.renderCharts();
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            // Fournir des données par défaut en cas d'erreur
            this.state.bookingsData = {
                total: 0,
                confirmed: 0,
                pending: 0,
                cancelled: 0,
                recentBookings: [],
                genderData: [],
                airlineData: []
            };
        }
    }

    renderCharts() {
        console.log("renderCharts called");
        console.log("ApexCharts:", window.ApexCharts);
        console.log("Gender Data:", this.state.bookingsData.genderData);
        console.log("Airline Data:", this.state.bookingsData.airlineData);

        // Ensure ApexCharts is available
        if (typeof ApexCharts === 'undefined') {
            console.warn("ApexCharts library not loaded. Attempting to load dynamically.");
            this.loadApexChartsScript();
            return;
        }

        const genderChartElement = document.querySelector("#gender-chart");
        const airlineChartElement = document.querySelector("#airline-chart");

        if (!genderChartElement || !airlineChartElement) {
            console.error("Chart container elements not found");
            return;
        }

        // Clear any existing charts
        genderChartElement.innerHTML = '';
        airlineChartElement.innerHTML = '';

        const { genderData, airlineData } = this.state.bookingsData;

        // Safety checks
        if (!genderData || genderData.length === 0) {
            genderChartElement.innerHTML = '<p>No gender data available</p>';
            return;
        }

        if (!airlineData || airlineData.length === 0) {
            airlineChartElement.innerHTML = '<p>No airline data available</p>';
            return;
        }

        try {
            // Gender Pie Chart with click event
            const genderChartOptions = {
                series: genderData.map(item => item.value),
                labels: genderData.map(item => item.name),
                chart: {
                    type: 'pie',
                    height: 350,
                    width: '100%',
                    events: {
                        dataPointSelection: (event, chartContext, config) => {
                            const selectedGender = config.w.config.labels[config.dataPointIndex];
                            this.openBookings([['gender', '=', selectedGender]]);
                        }
                    }
                },
                responsive: [{
                    breakpoint: 480,
                    options: {
                        chart: { width: 200 },
                        legend: { position: 'bottom' }
                    }
                }],
                title: {
                    text: 'Gender Distribution (Click to Filter)',
                    align: 'left'
                },
                // Ensure color differentiation
                colors: ['#008FFB', '#00E396', '#FEB019', '#FF4560', '#775DD0']
            };

            // Airline Horizontal Bar Chart with click event
            const airlineChartOptions = {
                series: [{
                    name: 'Bookings',
                    data: airlineData.map(item => item.value)
                }],
                chart: {
                    type: 'bar',
                    height: 350,
                    width: '100%',
                    events: {
                        dataPointSelection: (event, chartContext, config) => {
                            const selectedAirline = config.w.config.xaxis.categories[config.dataPointIndex];
                            this.openBookings([['airline', '=', selectedAirline]]);
                        }
                    }
                },
                plotOptions: {
                    bar: {
                        borderRadius: 4,
                        horizontal: true,
                    }
                },
                dataLabels: {
                    enabled: true,
                    formatter: function (val) {
                        return val.toString();
                    }
                },
                xaxis: {
                    categories: airlineData.map(item => item.name)
                },
                title: {
                    text: 'Airline Bookings (Click to Filter)',
                    align: 'left'
                },
                colors: ['#008FFB']
            };

            // Render charts with error handling
            new ApexCharts(genderChartElement, genderChartOptions).render();
            new ApexCharts(airlineChartElement, airlineChartOptions).render();

        } catch (renderError) {
            console.error("Chart Rendering Error:", renderError);
            genderChartElement.innerHTML = '<p>Error rendering gender chart</p>';
            airlineChartElement.innerHTML = '<p>Error rendering airline chart</p>';
        }
    }

    loadApexChartsScript() {
        const script = document.createElement('script');
        script.src = '/travel_booking/static/lib/apexcharts.min.js';
        script.onload = () => {
            console.log("ApexCharts script loaded successfully");
            this.renderCharts();
        };
        script.onerror = (error) => {
            console.error("ApexCharts script loading failed:", error);
        };
        document.head.appendChild(script);
    }

    openBookings(domain) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Bookings',
            res_model: 'booking',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: domain,
        });
    }

    openRecentBooking(bookingId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Booking Details',
            res_model: 'booking',
            view_mode: 'form',
            views: [[false, 'form']],
            res_id: bookingId,
            target: 'current',
        });
    }
}

registry.category("actions").add("travel_booking_dashboard", BookingDashboard);