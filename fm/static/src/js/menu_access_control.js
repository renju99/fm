/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { Menu } from "@web/webclient/menu/menu";

// Patch the Menu component to hide facilities management menus for users without proper groups
patch(Menu.prototype, {
    async setup() {
        await super.setup();
        this._checkFacilitiesMenuAccess();
    },

    _checkFacilitiesMenuAccess() {
        // Get user groups from the session
        const userGroups = this.env.services.user.groups || [];
        
        // Define facilities management group names
        const facilitiesGroups = [
            'Facilities Management User',
            'Facilities Management Manager', 
            'Facilities Technician',
            'Facilities Focused User'
        ];
        
        // Check if user has any facilities management groups
        const hasFacilitiesAccess = facilitiesGroups.some(group => 
            userGroups.some(userGroup => userGroup.includes(group))
        );
        
        console.log('User groups:', userGroups);
        console.log('Has facilities access:', hasFacilitiesAccess);
        
        // Hide facilities management menus if user doesn't have access
        if (!hasFacilitiesAccess) {
            this._hideFacilitiesMenus();
        }
    },

    _hideFacilitiesMenus() {
        // List of facilities management menu IDs to hide
        const facilitiesMenuIds = [
            'menu_facilities_root',
            'menu_asset_management', 
            'menu_maintenance',
            'menu_space_booking',
            'menu_facilities_analytics',
            'menu_financial_management',
            'menu_vendor_management',
            'menu_safety_management',
            'menu_energy_management_root'
        ];
        
        // Hide each facilities management menu
        facilitiesMenuIds.forEach(menuId => {
            const menuElement = document.querySelector(`[data-menu-id="${menuId}"]`);
            if (menuElement) {
                menuElement.style.display = 'none';
                console.log(`Hidden menu: ${menuId}`);
            }
        });
        
        // Also hide by menu text content as fallback
        const menuTexts = [
            'Facilities',
            'Asset Management',
            'Maintenance', 
            'Space Booking',
            'Analytics',
            'Financial Management',
            'Vendor Management',
            'Safety & HSE',
            'Energy Management'
        ];
        
        menuTexts.forEach(menuText => {
            const menuElements = document.querySelectorAll(`[data-menu-id]`);
            menuElements.forEach(element => {
                if (element.textContent.trim() === menuText) {
                    element.style.display = 'none';
                    console.log(`Hidden menu by text: ${menuText}`);
                }
            });
        });
    }
});

// Additional service to check menu access
const menuAccessService = {
    name: "menu_access",
    
    start(env, { services }) {
        return {
            checkFacilitiesAccess() {
                const userGroups = services.user.groups || [];
                const facilitiesGroups = [
                    'Facilities Management User',
                    'Facilities Management Manager',
                    'Facilities Technician', 
                    'Facilities Focused User'
                ];
                
                return facilitiesGroups.some(group => 
                    userGroups.some(userGroup => userGroup.includes(group))
                );
            }
        };
    }
};

registry.category("services").add("menu_access", menuAccessService);
