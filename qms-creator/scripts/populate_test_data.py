#!/usr/bin/env python3
"""
Populate Test Data for Cannabis EU GMP QMS Creator
Fills facility_data.yaml with test data for initial testing
"""

import yaml
from pathlib import Path
from datetime import datetime, timedelta


def create_test_data():
    """Create test facility data."""
    test_data = {
        'company': {
            'legal_entity_name': 'Purely Plant GmbH',
            'registration_number': 'MK-REG-2024-001',
            'facility_name': 'Purely Plant Medical Cannabis Production Facility',
            'address': {
                'street': '123 Cannabis Boulevard',
                'city': 'Skopje',
                'region': 'Skopje Region',
                'postal_code': '1000',
                'country': 'North Macedonia',
                'latitude': '41.9973',
                'longitude': '21.4280'
            }
        },

        'regulatory': {
            'medical_cannabis_license': {
                'license_number': 'MK-MED-CANNABIS-2024-001',
                'issue_date': '2024-01-15',
                'expiration_date': '2027-01-15'
            },
            'regulatory_authority': {
                'name': 'Ministry of Health of North Macedonia',
                'contact_name': 'Dr. Ivana Petrov',
                'phone': '+389 2 3123 456',
                'email': 'cannabis.licensing@health.gov.mk'
            },
            'secondary_authorities': {
                'ministry_of_interior': {
                    'contact_name': 'Officer Aleksandar Dimitrov',
                    'phone': '+389 2 3123 789',
                    'email': 'security@interior.gov.mk'
                },
                'local_health_authority': {
                    'contact_name': 'Dr. Elena Stojanova',
                    'phone': '+389 2 3123 654',
                    'email': 'local.health@skopje.gov.mk'
                }
            }
        },

        'personnel': {
            'qualified_person': {
                'first_name': 'Blagoj',
                'last_name': 'Nikolov',
                'title': 'Qualified Person (QP)',
                'qualifications': 'Master Pharmacist, EU GMP Certified',
                'phone': '+389 70 123 456',
                'email': 'blagoj.nikolov@purelyplant.mk'
            },
            'facility_manager': {
                'first_name': 'Stefan',
                'last_name': 'Petrov',
                'title': 'Facility Manager',
                'qualifications': 'BSc Agricultural Engineering',
                'phone': '+389 70 234 567',
                'email': 'stefan.petrov@purelyplant.mk'
            },
            'qa_manager': {
                'first_name': 'Ana',
                'last_name': 'Dimitrova',
                'title': 'Quality Assurance Manager',
                'qualifications': 'MSc Pharmaceutical Sciences',
                'phone': '+389 70 345 678',
                'email': 'ana.dimitrova@purelyplant.mk'
            },
            'production_manager': {
                'first_name': 'Marko',
                'last_name': 'Georgiev',
                'title': 'Production Manager',
                'qualifications': 'BSc Horticulture',
                'phone': '+389 70 456 789',
                'email': 'marko.georgiev@purelyplant.mk'
            },
            'sanitation_manager': {
                'first_name': 'Jovana',
                'last_name': 'Stankova',
                'title': 'Sanitation & Hygiene Manager',
                'qualifications': 'BSc Environmental Health',
                'phone': '+389 70 567 890',
                'email': 'jovana.stankova@purelyplant.mk'
            },
            'security_manager': {
                'first_name': 'Nikola',
                'last_name': 'Ivanovski',
                'title': 'Security Manager',
                'qualifications': 'Security Management Certificate',
                'phone': '+389 70 678 901',
                'email': 'nikola.ivanovski@purelyplant.mk'
            },
            'hr_manager': {
                'first_name': 'Katerina',
                'last_name': 'Trajkovska',
                'title': 'Human Resources Manager',
                'qualifications': 'MBA Human Resources',
                'phone': '+389 70 789 012',
                'email': 'katerina.trajkovska@purelyplant.mk'
            },
            'records_manager': {
                'first_name': 'Dejan',
                'last_name': 'Angelov',
                'title': 'Records Manager',
                'qualifications': 'BSc Information Management',
                'phone': '+389 70 890 123',
                'email': 'dejan.angelov@purelyplant.mk'
            }
        },

        'equipment': {
            'drying_machine': {
                'name': 'CDS24 Drying Machine',
                'model': 'CDS24',
                'manufacturer': 'Cannabis Drying Systems Inc.',
                'serial_number': 'CDS24-2023-1045',
                'equipment_id': 'EQU-DRYING-001',
                'location': 'Processing Room (Room 07)',
                'calibration_due_date': '2026-06-15',
                'qualification_status': 'QUALIFIED'
            },
            'trimming_machine': {
                'name': 'MT Tumbler Machine',
                'model': 'MT-500',
                'manufacturer': 'Medical Trimming Technologies',
                'serial_number': 'MT500-2023-0892',
                'equipment_id': 'EQU-TRIM-001',
                'location': 'Processing Room (Room 07)',
                'calibration_due_date': '2026-06-15',
                'qualification_status': 'QUALIFIED'
            },
            'packaging_equipment': {
                'name': 'Automated Packaging System',
                'model': 'APS-2000',
                'manufacturer': 'PackPro Medical',
                'serial_number': 'APS2000-2023-0445',
                'equipment_id': 'EQU-PKG-001',
                'location': 'Packaging Room (Room 08)',
                'calibration_due_date': '2026-07-01',
                'qualification_status': 'QUALIFIED'
            },
            'hvac_system': {
                'name': 'HVAC Climate Control System',
                'model': 'ClimateMax Pro 5000',
                'manufacturer': 'HVAC Solutions Europe',
                'serial_number': 'CMP5000-2023-0234',
                'equipment_id': 'EQU-HVAC-001',
                'location': 'Facility-wide',
                'calibration_due_date': '2026-03-30',
                'qualification_status': 'QUALIFIED'
            },
            'irrigation_system': {
                'name': 'Automated Irrigation System',
                'model': 'AutoGrow 300',
                'manufacturer': 'AgriTech Systems',
                'serial_number': 'AG300-2023-1123',
                'equipment_id': 'EQU-IRR-001',
                'location': 'Cultivation Rooms (Rooms 02-05)',
                'calibration_due_date': '2026-04-15',
                'qualification_status': 'QUALIFIED'
            },
            'lighting_system': {
                'name': 'LED Grow Lights',
                'type': 'Full Spectrum LED 1000W',
                'manufacturer': 'GrowLight Pro',
                'equipment_id': 'EQU-LIGHT-001',
                'location': 'Cultivation Rooms (Rooms 02-05)',
                'calibration_due_date': '2026-08-01'
            },
            'water_system': {
                'name': 'RO Water Purification System',
                'model': 'PureWater RO-500',
                'manufacturer': 'Water Systems International',
                'serial_number': 'PWRO500-2023-0667',
                'equipment_id': 'EQU-WATER-001',
                'location': 'Utility Room',
                'calibration_due_date': '2026-05-20',
                'qualification_status': 'QUALIFIED'
            },
            'waste_system': {
                'name': 'Cannabis Waste Disposal System',
                'type': 'Approved Destruction Method',
                'equipment_id': 'EQU-WASTE-001',
                'location': 'Waste Storage Area'
            },
            'instruments': {
                'instrument_1': {
                    'name': 'Moisture Content Analyzer',
                    'model': 'MCA-100',
                    'serial_number': 'MCA100-2023-0234',
                    'equipment_id': 'EQU-QC-001',
                    'calibration_due_date': '2026-09-01'
                },
                'instrument_2': {
                    'name': 'Digital pH Meter',
                    'model': 'pH-Pro 200',
                    'serial_number': 'PHM200-2023-0456',
                    'equipment_id': 'EQU-QC-002',
                    'calibration_due_date': '2026-09-15'
                },
                'instrument_3': {
                    'name': 'Temperature/Humidity Logger',
                    'model': 'TempLog 500',
                    'serial_number': 'TL500-2023-0789',
                    'equipment_id': 'EQU-QC-003',
                    'calibration_due_date': '2026-10-01'
                }
            }
        },

        'facilities': {
            'total_area_sqm': '2500',
            'rooms': [
                {
                    'room_id': 'ROOM-01',
                    'name': 'Reception & Material Intake',
                    'area_sqm': '150',
                    'classification': 'GACP',
                    'purpose': 'Material receiving and initial inspection'
                },
                {
                    'room_id': 'ROOM-02',
                    'name': 'Propagation Room',
                    'area_sqm': '200',
                    'classification': 'GACP',
                    'purpose': 'Plant propagation and early growth'
                },
                {
                    'room_id': 'ROOM-03',
                    'name': 'Vegetative Growth Room',
                    'area_sqm': '400',
                    'classification': 'GACP',
                    'purpose': 'Vegetative cannabis cultivation'
                },
                {
                    'room_id': 'ROOM-04',
                    'name': 'Flowering Room 1',
                    'area_sqm': '500',
                    'classification': 'GACP',
                    'purpose': 'Cannabis flowering stage'
                },
                {
                    'room_id': 'ROOM-05',
                    'name': 'Flowering Room 2',
                    'area_sqm': '500',
                    'classification': 'GACP',
                    'purpose': 'Cannabis flowering stage'
                },
                {
                    'room_id': 'ROOM-06',
                    'name': 'Drying & Curing Room',
                    'area_sqm': '250',
                    'classification': 'GMP Grade D',
                    'purpose': 'Post-harvest drying and curing'
                },
                {
                    'room_id': 'ROOM-07',
                    'name': 'Trimming & Processing Room',
                    'area_sqm': '200',
                    'classification': 'GMP Grade D',
                    'purpose': 'Cannabis trimming and processing'
                },
                {
                    'room_id': 'ROOM-08',
                    'name': 'Packaging Room',
                    'area_sqm': '150',
                    'classification': 'GMP Grade D',
                    'purpose': 'Final product packaging'
                },
                {
                    'room_id': 'ROOM-09',
                    'name': 'Secure Storage Vault',
                    'area_sqm': '150',
                    'classification': 'High Security',
                    'purpose': 'Finished product storage'
                }
            ],
            'storage': {
                'primary_document_storage': 'Quality Assurance Office, Server Room',
                'backup_document_storage': 'Off-site Cloud Storage + Local Backup Server',
                'archive_storage': 'Dedicated Archive Room (Climate Controlled)',
                'secure_vault': 'Secure Storage Vault (Room 09)',
                'controlled_substance_storage': 'Secure Storage Vault (Room 09)'
            }
        },

        'operations': {
            'scope': {
                'cultivation': True,
                'flowering': True,
                'harvesting': True,
                'drying_curing': True,
                'processing': True,
                'packaging': True,
                'quality_control': True,
                'distribution': False
            },
            'additional_operations': 'Post-harvest quality testing (in-house moisture and visual inspection)',
            'excluded_operations': 'Product distribution and retail sales (handled by licensed distributors)',
            'quality_objectives': {
                'objective_1': 'Zero critical deviations per quarter',
                'objective_2': '100% batch release compliance with specifications',
                'objective_3': '95%+ personnel training completion rate',
                'custom_objectives': [
                    'Maintain environmental monitoring within specifications 99% of the time',
                    'Complete all equipment calibrations 30 days before due date'
                ]
            },
            'metrics': {
                'target_metric_1': 'Potency variance: ±10% of label claim',
                'target_metric_2': 'Microbial contamination: <100 CFU/g',
                'target_metric_3': 'Batch release time: <7 days from harvest'
            }
        },

        'quality_control': {
            'in_house_lab': False,
            'contract_lab': True,
            'contract_lab_details': {
                'name': 'Eurofins Analytical Laboratory',
                'address': 'Industrial Zone, Skopje, North Macedonia',
                'contact_name': 'Dr. Zoran Petrov',
                'phone': '+389 2 3456 789',
                'email': 'cannabis@eurofins.mk',
                'accreditation': 'ISO/IEC 17025:2017'
            },
            'testing_capabilities': {
                'potency_testing': 'Contract Lab',
                'microbial_testing': 'Contract Lab',
                'pesticide_testing': 'Contract Lab',
                'heavy_metals_testing': 'Contract Lab',
                'moisture_content': 'In-house',
                'visual_inspection': 'In-house'
            }
        },

        'document_control': {
            'retention_periods': {
                'batch_records': '7 years',
                'training_records': '7 years',
                'equipment_qualification': 'Life of equipment + 1 year',
                'deviation_reports': '7 years',
                'audit_reports': '7 years',
                'qms_documents': 'Permanent (superseded versions: 3 years)'
            },
            'controlled_locations': [
                'Quality Assurance Office',
                'Production Supervisor Office',
                'Facility Manager Office'
            ],
            'access_control': {
                'procedure': 'Restricted access - authorized personnel only with secure login credentials',
                'backup_frequency': 'Daily automated backup at 23:00 CET'
            }
        },

        'metadata': {
            'qms_version': '1.0',
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'effective_date': '2026-02-01',
            'next_review_date': '2027-02-01',
            'generated_by': 'Cannabis EU GMP QMS Creator - Automation System',
            'generation_date': ''
        }
    }

    return test_data


def main():
    """Main function to populate test data."""
    print("Populating test data...")

    # Get config directory
    base_dir = Path(__file__).parent.parent
    config_path = base_dir / 'config' / 'facility_data.yaml'

    # Create test data
    test_data = create_test_data()

    # Write to YAML file
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(test_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"✓ Test data written to: {config_path}")
    print("\nTest data includes:")
    print("  • Complete company and facility information")
    print("  • 8 personnel with full contact details")
    print("  • 10+ equipment systems with serial numbers")
    print("  • 9 rooms with areas and classifications")
    print("  • Quality objectives and metrics")
    print("  • Contract lab details")
    print("\nYou can now run: python scripts/customize_documents.py --all")


if __name__ == "__main__":
    main()
