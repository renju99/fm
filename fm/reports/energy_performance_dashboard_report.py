# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class EnergyPerformanceDashboardReport(models.AbstractModel):
    _name = 'report.fm.energy_performance_dashboard'
    _description = 'Energy Performance Dashboard Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for the energy performance dashboard."""
        docs = self.env['facilities.energy.performance.dashboard'].browse(docids)
        
        # Process each document to ensure all required fields are computed
        for doc in docs:
            # Force computation of metrics if not already done
            if doc.state == 'draft':
                doc.action_process()
            
            self._process_dashboard_data(doc)
        
        return {
            'doc_ids': docids,
            'doc_model': 'facilities.energy.performance.dashboard',
            'docs': docs,
            'data': data,
            'get_report_data': self._get_report_data,
        }

    def _process_dashboard_data(self, doc):
        """Process and enhance dashboard data for reporting."""
        try:
            # Ensure the dashboard has been processed
            if doc.state != 'completed':
                doc.action_process()
            
            # All data should now be computed via the dashboard model's _compute_metrics method
            # No need for hardcoded default values anymore
            
            # Log current values for debugging
            _logger.info(f"Dashboard {doc.name} metrics - Meters: {doc.total_meters}, "
                        f"Consumption: {doc.total_consumption}, Cost: {doc.total_energy_cost}, "
                        f"Efficiency: {doc.avg_efficiency_score}%")
            
        except Exception as e:
            _logger.error(f"Error processing dashboard data: {str(e)}")
            raise UserError(_("Unable to process dashboard data: %s") % str(e))

    def _get_report_data(self, doc):
        """Get additional report data for the dashboard."""
        return {
            'summary_metrics': self._get_summary_metrics(doc),
            'performance_trends': self._get_performance_trends(doc),
            'financial_analysis': self._get_financial_analysis(doc),
            'efficiency_insights': self._get_efficiency_insights(doc),
            'consumption_analysis': self._get_consumption_analysis(doc),
            'environmental_impact': self._get_environmental_impact(doc),
        }

    def _get_summary_metrics(self, doc):
        """Get summary metrics for the dashboard."""
        return {
            'total_meters': doc.total_meters,
            'total_consumption': doc.total_consumption,
            'total_energy_cost': doc.total_energy_cost,
            'avg_efficiency_score': doc.avg_efficiency_score,
            'sustainability_score': doc.sustainability_score,
            'co2_emissions': doc.co2_emissions,
            'utilization_rate': doc.utilization_rate,
        }

    def _get_performance_trends(self, doc):
        """Get performance trends data based on historical analysis."""
        # Calculate trends by comparing with previous periods
        try:
            # Look for previous dashboard analysis for the same facility/meters
            previous_dashboard = self.env['facilities.energy.performance.dashboard'].search([
                ('facility_id', '=', doc.facility_id.id if doc.facility_id else False),
                ('date_to', '<', doc.date_from),
                ('state', '=', 'completed')
            ], limit=1, order='date_to desc')
            
            if previous_dashboard:
                consumption_trend = doc.trend_percentage
                efficiency_trend = doc.avg_efficiency_score - previous_dashboard.avg_efficiency_score
                cost_trend = ((doc.total_energy_cost - previous_dashboard.total_energy_cost) / 
                             previous_dashboard.total_energy_cost * 100) if previous_dashboard.total_energy_cost > 0 else 0
                sustainability_trend = doc.sustainability_score - previous_dashboard.sustainability_score
                
                return {
                    'consumption_trend': f"{'+' if consumption_trend >= 0 else ''}{consumption_trend:.1f}%",
                    'efficiency_trend': f"{'+' if efficiency_trend >= 0 else ''}{efficiency_trend:.1f}%",
                    'cost_trend': f"{'+' if cost_trend >= 0 else ''}{cost_trend:.1f}%",
                    'sustainability_trend': f"{'+' if sustainability_trend >= 0 else ''}{sustainability_trend:.1f}%",
                }
            else:
                return {
                    'consumption_trend': 'N/A (First Analysis)',
                    'efficiency_trend': 'N/A (First Analysis)',
                    'cost_trend': 'N/A (First Analysis)',
                    'sustainability_trend': 'N/A (First Analysis)',
                }
        except Exception as e:
            _logger.warning(f"Could not calculate trends: {str(e)}")
            return {
                'consumption_trend': 'N/A',
                'efficiency_trend': 'N/A',
                'cost_trend': 'N/A',
                'sustainability_trend': 'N/A',
            }

    def _get_financial_analysis(self, doc):
        """Get financial analysis data."""
        return {
            'total_energy_cost': doc.total_energy_cost,
            'electricity_cost': doc.electricity_cost,
            'water_cost': doc.water_cost,
            'gas_cost': doc.gas_cost,
            'steam_cost': doc.steam_cost,
            'cost_per_sqm': doc.cost_per_sqm,
            'cost_per_occupant': doc.cost_per_occupant,
            'cost_per_hour': doc.cost_per_hour,
            'industry_benchmark_cost': doc.industry_benchmark_cost,
            'benchmark_performance': doc.benchmark_performance,
        }

    def _get_efficiency_insights(self, doc):
        """Get efficiency insights data based on actual performance records."""
        try:
            # Get consumption records for the analysis period
            consumption_domain = [
                ('reading_date', '>=', doc.date_from),
                ('reading_date', '<=', doc.date_to),
                ('is_validated', '=', True)
            ]
            
            if doc.facility_id:
                consumption_domain.append(('meter_id.facility_id', '=', doc.facility_id.id))
            elif doc.meter_ids:
                consumption_domain.append(('meter_id', 'in', doc.meter_ids.ids))
            
            consumption_records = self.env['facilities.energy.consumption'].search(consumption_domain)
            
            if consumption_records:
                # Calculate actual efficiency insights
                total_records = len(consumption_records)
                anomaly_records = len(consumption_records.filtered(lambda r: r.is_anomaly))
                high_consumption_records = len(consumption_records.filtered(
                    lambda r: r.anomaly_severity in ['high', 'critical']
                ))
                
                # Calculate efficiency by meter type
                electricity_records = consumption_records.filtered(lambda r: r.meter_id.meter_type == 'electricity')
                water_records = consumption_records.filtered(lambda r: r.meter_id.meter_type == 'water')
                gas_records = consumption_records.filtered(lambda r: r.meter_id.meter_type == 'gas')
                steam_records = consumption_records.filtered(lambda r: r.meter_id.meter_type == 'steam')
                
                return {
                    'energy_efficiency_score': doc.energy_efficiency_score,
                    'water_efficiency_score': doc.water_efficiency_score,
                    'sustainability_score': doc.sustainability_score,
                    'anomaly_rate': (anomaly_records / total_records * 100) if total_records else 0,
                    'high_consumption_rate': (high_consumption_records / total_records * 100) if total_records else 0,
                    'total_consumption_records': total_records,
                    'electricity_records': len(electricity_records),
                    'water_records': len(water_records),
                    'gas_records': len(gas_records),
                    'steam_records': len(steam_records),
                    'peak_demand': doc.peak_demand,
                    'average_demand': doc.average_demand,
                    'load_factor': doc.load_factor,
                }
            else:
                # No consumption records found
                return {
                    'energy_efficiency_score': 0,
                    'water_efficiency_score': 0,
                    'sustainability_score': 0,
                    'anomaly_rate': 0,
                    'high_consumption_rate': 0,
                    'total_consumption_records': 0,
                    'electricity_records': 0,
                    'water_records': 0,
                    'gas_records': 0,
                    'steam_records': 0,
                    'peak_demand': 0,
                    'average_demand': 0,
                    'load_factor': 0,
                }
        except Exception as e:
            _logger.error(f"Error calculating efficiency insights: {str(e)}")
            return {
                'energy_efficiency_score': doc.energy_efficiency_score or 0,
                'water_efficiency_score': doc.water_efficiency_score or 0,
                'sustainability_score': doc.sustainability_score or 0,
                'anomaly_rate': 5.0,  # Default fallback
                'high_consumption_rate': 2.0,
                'total_consumption_records': 0,
                'electricity_records': 0,
                'water_records': 0,
                'gas_records': 0,
                'steam_records': 0,
                'peak_demand': doc.peak_demand or 0,
                'average_demand': doc.average_demand or 0,
                'load_factor': doc.load_factor or 0,
            }

    def _get_consumption_analysis(self, doc):
        """Get consumption analysis data."""
        try:
            # Get consumption records for the analysis period
            consumption_domain = [
                ('reading_date', '>=', doc.date_from),
                ('reading_date', '<=', doc.date_to),
                ('is_validated', '=', True)
            ]
            
            if doc.facility_id:
                consumption_domain.append(('meter_id.facility_id', '=', doc.facility_id.id))
            elif doc.meter_ids:
                consumption_domain.append(('meter_id', 'in', doc.meter_ids.ids))
            
            consumption_records = self.env['facilities.energy.consumption'].search(consumption_domain)
            
            # Categorize consumption by meter type
            electricity_consumption = sum(consumption_records.filtered(
                lambda r: r.meter_id.meter_type == 'electricity'
            ).mapped('consumption'))
            water_consumption = sum(consumption_records.filtered(
                lambda r: r.meter_id.meter_type == 'water'
            ).mapped('consumption'))
            gas_consumption = sum(consumption_records.filtered(
                lambda r: r.meter_id.meter_type == 'gas'
            ).mapped('consumption'))
            steam_consumption = sum(consumption_records.filtered(
                lambda r: r.meter_id.meter_type == 'steam'
            ).mapped('consumption'))
            
            # Calculate consumption by facility
            facility_consumption = {}
            for record in consumption_records:
                facility_name = record.meter_id.facility_id.name if record.meter_id.facility_id else 'Unknown'
                if facility_name not in facility_consumption:
                    facility_consumption[facility_name] = 0
                facility_consumption[facility_name] += record.consumption
            
            # Get top consuming meters
            meter_consumption = {}
            for record in consumption_records:
                meter_name = record.meter_id.name
                if meter_name not in meter_consumption:
                    meter_consumption[meter_name] = 0
                meter_consumption[meter_name] += record.consumption
            
            top_meters = sorted(meter_consumption.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                'total_consumption': doc.total_consumption,
                'electricity_consumption': doc.electricity_consumption,
                'water_consumption': doc.water_consumption,
                'gas_consumption': doc.gas_consumption,
                'steam_consumption': doc.steam_consumption,
                'consumption_trend': doc.consumption_trend,
                'trend_percentage': doc.trend_percentage,
                'facility_consumption': facility_consumption,
                'top_consuming_meters': top_meters,
                'total_consumption_records': len(consumption_records),
                'facility_filter': doc.facility_id.name if doc.facility_id else None,
            }
        except Exception as e:
            _logger.error(f"Error calculating consumption analysis: {str(e)}")
            return {
                'total_consumption': doc.total_consumption or 0,
                'electricity_consumption': doc.electricity_consumption or 0,
                'water_consumption': doc.water_consumption or 0,
                'gas_consumption': doc.gas_consumption or 0,
                'steam_consumption': doc.steam_consumption or 0,
                'consumption_trend': doc.consumption_trend or 'stable',
                'trend_percentage': doc.trend_percentage or 0,
                'facility_consumption': {},
                'top_consuming_meters': [],
                'total_consumption_records': 0,
                'facility_filter': doc.facility_id.name if doc.facility_id else None,
            }

    def _get_environmental_impact(self, doc):
        """Get environmental impact data."""
        return {
            'co2_emissions': doc.co2_emissions,
            'sustainability_score': doc.sustainability_score,
            'energy_efficiency_score': doc.energy_efficiency_score,
            'water_efficiency_score': doc.water_efficiency_score,
            'renewable_energy_percentage': 0,  # Placeholder for future implementation
            'carbon_intensity': doc.co2_emissions / doc.total_consumption if doc.total_consumption > 0 else 0,
            'environmental_rating': self._get_environmental_rating(doc.sustainability_score),
        }

    def _get_environmental_rating(self, sustainability_score):
        """Get environmental rating based on sustainability score."""
        if sustainability_score >= 90:
            return 'Excellent'
        elif sustainability_score >= 80:
            return 'Very Good'
        elif sustainability_score >= 70:
            return 'Good'
        elif sustainability_score >= 60:
            return 'Fair'
        else:
            return 'Poor'
