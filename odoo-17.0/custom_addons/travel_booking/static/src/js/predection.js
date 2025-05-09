odoo.define('travel_booking.booking_prediction_dashboard', function (require) {
    'use strict';

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');
    const rpc = require('web.rpc');
    const _t = core._t;

    const PredictionDashboard = AbstractAction.extend({
        template: 'travel_booking.PredictionDashboard',
        events: {
            'change .period-selector': '_onPeriodChange',
            'click .refresh-data': '_refreshData',
            'click .generate-predictions': '_openPredictionWizard'
        },

        /**
         * @override
         */
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.actionManager = parent;
            this.selectedPeriod = 'monthly';
            this.charts = {};
        },

        /**
         * @override
         */
        start: function () {
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadData()
            ]);
        },

        /**
         * Load prediction data from the server
         * @private
         */
        _loadData: function () {
            const self = this;
            return rpc.query({
                model: 'booking.airline.prediction',
                method: 'search_read',
                domain: [
                    ['prediction_period', '=', this.selectedPeriod]
                ],
                fields: ['airline', 'prediction_date', 'predicted_sales', 'actual_sales']
            }).then(function (result) {
                self.predictionData = result;
                self._renderDashboard();
            });
        },

        /**
         * Render dashboard with charts
         * @private
         */
        _renderDashboard: function () {
            const self = this;

            // Organize data by airline
            const airlineData = {};
            const uniqueAirlines = [];
            const uniqueDates = [];

            // First pass to collect unique airlines and dates
            this.predictionData.forEach(pred => {
                if (!uniqueAirlines.includes(pred.airline)) {
                    uniqueAirlines.push(pred.airline);
                    airlineData[pred.airline] = [];
                }

                const date = pred.prediction_date.split(' ')[0]; // Get just the date part
                if (!uniqueDates.includes(date)) {
                    uniqueDates.push(date);
                }
            });

            // Sort dates chronologically
            uniqueDates.sort();

            // Second pass to organize data by airline and date
            uniqueAirlines.forEach(airline => {
                uniqueDates.forEach(date => {
                    const predForDate = self.predictionData.find(
                        p => p.airline === airline && p.prediction_date.startsWith(date)
                    );

                    airlineData[airline].push({
                        x: date,
                        y: predForDate ? predForDate.predicted_sales : 0
                    });
                });
            });

            // Create the series for the chart
            const series = uniqueAirlines.map(airline => {
                return {
                    name: airline,
                    data: airlineData[airline]
                };
            });

            // Render the main chart
            this._renderMainChart(series, uniqueDates);

            // Render comparison charts
            this._renderComparisonCharts(uniqueAirlines, airlineData);

            // Render top airlines bar chart
            this._renderTopAirlinesChart(uniqueAirlines, airlineData);
        },

        /**
         * Render the main line chart with all airlines
         * @private
         */
        _renderMainChart: function (series, categories) {
            const $mainChart = this.$('.main-prediction-chart');

            if (this.charts.mainChart) {
                this.charts.mainChart.destroy();
            }

            const options = {
                chart: {
                    type: 'line',
                    height: 350,
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 800
                    },
                    toolbar: {
                        show: true,
                        tools: {
                            download: true,
                            selection: true,
                            zoom: true,
                            zoomin: true,
                            zoomout: true,
                            pan: true,
                            reset: true
                        }
                    }
                },
                series: series,
                xaxis: {
                    type: 'datetime',
                    title: {
                        text: _t('Date')
                    }
                },
                yaxis: {
                    title: {
                        text: _t('Ventes prévues')
                    }
                },
                tooltip: {
                    x: {
                        format: 'dd MMM yyyy'
                    }
                },
                legend: {
                    position: 'top'
                },
                title: {
                    text: _t('Prédictions des ventes par compagnie aérienne'),
                    align: 'center'
                },
                noData: {
                    text: _t('Aucune donnée disponible')
                }
            };

            this.charts.mainChart = new ApexCharts($mainChart[0], options);
            this.charts.mainChart.render();
        },

        /**
         * Render comparison charts for predicted vs actual sales
         * @private
         */
        _renderComparisonCharts: function (airlines, airlineData) {
            const self = this;
            const $comparisonChartsContainer = this.$('.comparison-charts-container');

            // Clear previous charts
            $comparisonChartsContainer.empty();

            // Create a comparison chart for each airline
            airlines.forEach((airline, index) => {
                // Create container for this airline's chart
                const $chartContainer = $('<div>', {
                    class: 'airline-comparison-chart mb-4',
                    'data-airline': airline
                });

                const $chartTitle = $('<h5>', {
                    class: 'text-center mb-3',
                    text: airline
                });

                const $chart = $('<div>', {
                    id: `airline-chart-${index}`
                });

                $chartContainer.append($chartTitle, $chart);
                $comparisonChartsContainer.append($chartContainer);

                // Prepare data for comparison (predicted vs actual)
                const predictedData = [];
                const actualData = [];

                airlineData[airline].forEach(point => {
                    const predForDate = self.predictionData.find(
                        p => p.airline === airline && p.prediction_date.startsWith(point.x)
                    );

                    predictedData.push({
                        x: point.x,
                        y: point.y
                    });

                    actualData.push({
                        x: point.x,
                        y: predForDate && predForDate.actual_sales ? predForDate.actual_sales : null
                    });
                });

                // Create comparison chart
                const compSeries = [
                    {
                        name: _t('Prédictions'),
                        data: predictedData
                    },
                    {
                        name: _t('Ventes réelles'),
                        data: actualData
                    }
                ];

                const compOptions = {
                    chart: {
                        type: 'line',
                        height: 250,
                        toolbar: {
                            show: true,
                            tools: {
                                download: true,
                                selection: false,
                                zoom: false,
                                zoomin: false,
                                zoomout: false,
                                pan: false,
                                reset: false
                            }
                        }
                    },
                    series: compSeries,
                    colors: ['#3498db', '#2ecc71'],
                    xaxis: {
                        type: 'datetime'
                    },
                    yaxis: {
                        title: {
                            text: _t('Ventes')
                        }
                    },
                    tooltip: {
                        x: {
                            format: 'dd MMM yyyy'
                        }
                    },
                    legend: {
                        position: 'top'
                    }
                };

                const compChart = new ApexCharts($chart[0], compOptions);
                compChart.render();

                // Store the chart reference
                if (!this.charts.comparisonCharts) {
                    this.charts.comparisonCharts = [];
                }
                this.charts.comparisonCharts.push(compChart);
            });
        },

        /**
         * Render top airlines bar chart
         * @private
         */
        _renderTopAirlinesChart: function (airlines, airlineData) {
            const $topChart = this.$('.top-airlines-chart');

            if (this.charts.topChart) {
                this.charts.topChart.destroy();
            }

            // Calculate total predicted sales for each airline
            const airlineTotals = airlines.map(airline => {
                const total = airlineData[airline].reduce((sum, point) => sum + point.y, 0);
                return {
                    airline: airline,
                    total: total
                };
            });

            // Sort by total sales
            airlineTotals.sort((a, b) => b.total - a.total);

            // Take top 5 airlines
            const topAirlines = airlineTotals.slice(0, 5);

            const barOptions = {
                chart: {
                    type: 'bar',
                    height: 300
                },
                series: [{
                    name: _t('Ventes totales prédites'),
                    data: topAirlines.map(a => a.total)
                }],
                plotOptions: {
                    bar: {
                        horizontal: false,
                        columnWidth: '55%',
                        distributed: true
                    }
                },
                dataLabels: {
                    enabled: false
                },
                xaxis: {
                    categories: topAirlines.map(a => a.airline),
                    labels: {
                        rotate: -45,
                        style: {
                            fontSize: '12px'
                        }
                    }
                },
                title: {
                    text: _t('Top 5 des compagnies aériennes par ventes prédites'),
                    align: 'center'
                },
                colors: ['#1abc9c', '#2ecc71', '#3498db', '#9b59b6', '#f1c40f']
            };

            this.charts.topChart = new ApexCharts($topChart[0], barOptions);
            this.charts.topChart.render();
        },

        /**
         * Handle period change
         * @private
         */
        _onPeriodChange: function (ev) {
            this.selectedPeriod = $(ev.target).val();
            this._loadData();
        },

        /**
         * Refresh dashboard data
         * @private
         */
        _refreshData: function () {
            this._loadData();
        },

        /**
         * Open prediction generation wizard
         * @private
         */
        _openPredictionWizard: function () {
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'booking.generate.predictions.wizard',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    'default_prediction_period': this.selectedPeriod
                }
            });
        }
    });

    core.action_registry.add('booking_prediction_dashboard', PredictionDashboard);

    return PredictionDashboard;
});