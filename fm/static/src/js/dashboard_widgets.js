/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

class FacilitiesDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            dashboardData: null,
            isLoading: true,
        });
        
        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            const data = await this.orm.call(
                "facilities.space.booking",
                "get_dashboard_data",
                []
            );
            this.state.dashboardData = data;
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.notification.add(
                "Error loading dashboard data",
                { type: "danger" }
            );
            this.state.isLoading = false;
        }
    }
}

FacilitiesDashboard.template = "facilities_management.FacilitiesDashboard";
FacilitiesDashboard.components = { Layout };

// Commenting out registration since this component is not currently used
// registry.category("actions").add("facilities_dashboard", FacilitiesDashboard);

// Basic utility functions
window.facilitiesUtils = {
    formatCurrency: function(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },

    formatDate: function(date) {
        return new Date(date).toLocaleDateString();
    },

    getSLAStatusClass: function(status) {
        const statusClasses = {
            'on_time': 'o_sla_on_time',
            'warning': 'o_sla_warning',
            'critical': 'o_sla_critical',
            'breached': 'o_sla_breached'
        };
        return statusClasses[status] || 'o_sla_on_time';
    }
};

console.log("Facilities Management JavaScript loaded");