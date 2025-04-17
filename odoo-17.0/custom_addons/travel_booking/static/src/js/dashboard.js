```jsx
import React, { useState, useEffect } from 'react';
import { 
    PieChart, Pie, BarChart, Bar, 
    XAxis, YAxis, CartesianGrid, 
    Tooltip, Legend, ResponsiveContainer 
} from 'recharts';

// Custom Chart Components
const ChartWrapper = ({ title, children, isEmpty }) => (
    <div className="card mb-4">
        <div className="card-header">
            <h5 className="card-title">{title}</h5>
        </div>
        <div className="card-body" style={{ minHeight: 300 }}>
            {isEmpty ? (
                <div className="d-flex justify-content-center align-items-center h-100 text-muted">
                    No data available
                </div>
            ) : (
                children
            )}
        </div>
    </div>
);

const PieChartComponent = ({ data, title }) => (
    <ResponsiveContainer width="100%" height={300}>
        <PieChart>
            <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            />
            <Tooltip />
            <Legend />
        </PieChart>
    </ResponsiveContainer>
);

const BarChartComponent = ({ data, title, dataKey = "value" }) => (
    <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey={dataKey} fill="#82ca9d" />
        </BarChart>
    </ResponsiveContainer>
);

const DualAxisBarChart = ({ data }) => (
    <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis yAxisId="left" label={{ value: 'Booking Count', angle: -90, position: 'insideLeft' }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: 'Total Revenue', angle: 90, position: 'insideRight' }} />
            <Tooltip />
            <Legend />
            <Bar yAxisId="left" dataKey="bookingCount" fill="#8884d8" name="Booking Count" />
            <Bar yAxisId="right" dataKey="totalRevenue" fill="#82ca9d" name="Total Revenue" />
        </BarChart>
    </ResponsiveContainer>
);

// Main Dashboard Component
const BookingDashboard = () => {
    const [dashboardData, setDashboardData] = useState({
        total: 0,
        confirmed: 0,
        pending: 0,
        cancelled: 0,
        genderData: [],
        mealPreferenceData: [],
        passengerTypesData: [],
        paymentTrendsData: []
    });

    useEffect(() => {
        // Simulating Odoo RPC call - replace with actual Odoo method
        const fetchDashboardData = async () => {
            try {
                // These would be actual RPC calls in Odoo
                const genderData = await odoo.env['booking'].get_gender_distribution();
                const mealPreferenceData = await odoo.env['booking'].get_meal_preference_distribution();
                const passengerTypesData = await odoo.env['booking'].get_passenger_type_distribution();
                const paymentTrendsData = await odoo.env['booking'].get_payment_trends();
                
                const totalBookings = await odoo.env['booking'].search_count([]);
                const confirmedBookings = await odoo.env['booking'].search_count([['state', '=', 'confirmed']]);
                const pendingBookings = await odoo.env['booking'].search_count([['state', '=', 'en attente de paiement']]);
                const cancelledBookings = await odoo.env['booking'].search_count([['state', '=', 'cancelled']]);
                const paymentMethodData = await odoo.env['booking'].get_payment_method_distribution();
                const ticketPriceRangeData = await odoo.env['booking'].get_ticket_price_ranges();

                setDashboardData({
                    total: totalBookings,
                    confirmed: confirmedBookings,
                    pending: pendingBookings,
                    cancelled: cancelledBookings,
                    genderData,
                    mealPreferenceData,
                    passengerTypesData,
                    paymentTrendsData,
                    paymentMethodData,
                    ticketPriceRangeData
                });
            } catch (error) {
                console.error("Error fetching dashboard data:", error);
            }
        };

        fetchDashboardData();
    }, []);

    const BookingStatCard = ({ title, value, color, onClick }) => (
        <div 
            className={`card text-center cursor-pointer hover-effect bg-${color}`} 
            onClick={onClick}
        >
            <div className="card-body">
                <h5 className="card-title text-white">{title}</h5>
                <p className="card-text display-4 text-white">{value}</p>
            </div>
        </div>
    );

    return (
        <div className="container-fluid o_travel_booking">
            <div className="row mb-4">
                <div className="col-12">
                    <h1 className="text-center">Travel Booking Dashboard</h1>
                </div>
            </div>

            {/* Booking Stats Cards */}
            <div className="row mb-4">
                <div className="col-3">
                    <BookingStatCard 
                        title="Total Bookings" 
                        value={dashboardData.total} 
                        color="primary" 
                        onClick={() => {/* Open all bookings */}}
                    />
                </div>
                <div className="col-3">
                    <BookingStatCard 
                        title="Confirmed" 
                        value={dashboardData.confirmed} 
                        color="success" 
                        onClick={() => {/* Open confirmed bookings */}}
                    />
                </div>
                <div className="col-3">
                    <BookingStatCard 
                        title="Pending" 
                        value={dashboardData.pending} 
                        color="warning" 
                        onClick={() => {/* Open pending bookings */}}
                    />
                </div>
                <div className="col-3">
                    <BookingStatCard 
                        title="Cancelled" 
                        value={dashboardData.cancelled} 
                        color="danger" 
                        onClick={() => {/* Open cancelled bookings */}}
                    />
                </div>
            </div>

            {/* Charts Row */}
            <div className="row">
                <div className="col-md-6">
                    <ChartWrapper 
                        title="Passenger Gender Distribution" 
                        isEmpty={!dashboardData.genderData.length}
                    >
                        <PieChartComponent 
                            data={dashboardData.genderData} 
                            title="Gender Distribution" 
                        />
                    </ChartWrapper>
                </div>
                <div className="col-md-6">
                    <ChartWrapper 
                        title="Meal Preference Distribution" 
                        isEmpty={!dashboardData.mealPreferenceData.length}
                    >
                        <BarChartComponent 
                            data={dashboardData.mealPreferenceData} 
                            title="Meal Preferences" 
                        />
                    </ChartWrapper>
                </div>
            </div>

            {/* Additional Charts Row */}
            <div className="row">
                <div className="col-md-6">
                    <ChartWrapper 
                        title="Passenger Types" 
                        isEmpty={!dashboardData.passengerTypesData.length}
                    >
                        <PieChartComponent 
                            data={dashboardData.passengerTypesData} 
                            title="Passenger Types" 
                        />
                    </ChartWrapper>
                </div>
                <div className="col-md-6">
                    <ChartWrapper 
                        title="Payment Trends" 
                        isEmpty={!dashboardData.paymentTrendsData.length}
                    >
                        <DualAxisBarChart 
                            data={dashboardData.paymentTrendsData} 
                        />
                    </ChartWrapper>
                </div>
            </div>
        </div>
    );
};

export default BookingDashboard;
```