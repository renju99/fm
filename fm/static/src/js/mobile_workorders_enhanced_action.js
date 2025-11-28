/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class MobileWorkordersEnhancedAction extends Component {
    static template = "facilities_management.MobileWorkordersEnhanced";

    setup() {
        this.orm = useService("orm");
        this.user = useService("user");
        this.action = useService("action");
        this.state = useState({
            myWorkorders: [],
            allWorkorders: [],
        });

        onWillStart(async () => {
            const myWoPromise = this.orm.searchRead(
                "facilities.workorder",
                ['|', ['technician_id.user_id', '=', this.user.userId], ['technician_ids.user_id', '=', this.user.userId]],
                ["name", "asset_id", "building_id", "priority", "sla_response_status", "sla_resolution_status", "status", "work_order_type"]
            );

            const allWoPromise = this.orm.searchRead(
                "facilities.workorder",
                [],
                ["name", "asset_id", "building_id", "priority", "sla_response_status", "sla_resolution_status", "status", "work_order_type"],
                { limit: 50 }
            );

            const [myWorkorders, allWorkorders] = await Promise.all([myWoPromise, allWoPromise]);
            this.state.myWorkorders = myWorkorders;
            this.state.allWorkorders = allWorkorders;
        });
    }

    openWorkorder(ev) {
        const workorderId = parseInt(ev.currentTarget.dataset.id);
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'facilities.workorder',
            res_id: workorderId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

registry.category("actions").add("mobile_workorders_enhanced", MobileWorkordersEnhancedAction);
