import pytest
from unittest.mock import Mock, patch, mock_open
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# Import the layers (assuming these exist in your project structure)
from risk_file_reader import RiskFileReader
from risk_filter_logic import RiskFilterLogic
from risk_table_formatter import RiskTableFormatter
from feature_integration import RiskAggregator


class TestRiskAggregatorIntegration:
    """Integration tests for Risk Aggregator feature"""
    
    @pytest.fixture
    def sample_risk_data(self):
        """Sample risk data for testing"""
        return pd.DataFrame({
            'risk_id': ['R001', 'R002', 'R003', 'R004', 'R005'],
            'risk_type': ['market', 'credit', 'operational', 'market', 'credit'],
            'severity': ['high', 'medium', 'low', 'critical', 'high'],
            'value': [100000, 50000, 10000, 500000, 75000],
            'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
            'department': ['trading', 'lending', 'operations', 'trading', 'lending']
        })
    
    @pytest.fixture
    def risk_aggregator(self):
        """Create RiskAggregator instance with mocked dependencies"""
        reader = RiskFileReader()
        filter_logic = RiskFilterLogic()
        formatter = RiskTableFormatter()
        return RiskAggregator(reader, filter_logic, formatter)
    
    @pytest.fixture
    def mock_file_content(self, sample_risk_data):
        """Mock CSV file content"""
        return sample_risk_data.to_csv(index=False)

    def test_read_filter_format_integration(self, risk_aggregator, sample_risk_data, mock_file_content):
        """Test complete flow: read file -> filter data -> format output"""
        # Mock file reading
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            with patch.object(RiskFileReader, 'read_csv', return_value=sample_risk_data):
                # Define filter criteria
                filter_criteria = {
                    'risk_type': ['market', 'credit'],
                    'severity': ['high', 'critical']
                }
                
                # Execute aggregation
                result = risk_aggregator.aggregate_risks(
                    file_path='risks.csv',
                    filter_criteria=filter_criteria,
                    output_format='table'
                )
                
                # Verify the result
                assert result is not None
                assert 'Total Risks' in result
                assert 'Risk Summary' in result
                assert 'market: 2' in result  # Should have 2 market risks
                assert 'credit: 1' in result  # Should have 1 credit risk
                assert 'Total Value at Risk: $675,000' in result

    def test_multiple_file_formats_integration(self, risk_aggregator, sample_risk_data):
        """Test reading different file formats and processing them"""
        file_formats = {
            'csv': sample_risk_data.to_csv(index=False),
            'json': sample_risk_data.to_json(orient='records'),
            'excel': None  # Would need actual Excel file bytes
        }
        
        for format_type, content in file_formats.items():
            if format_type == 'excel':
                continue  # Skip Excel for this example
                
            with patch('builtins.open', mock_open(read_data=content)):
                with patch.object(RiskFileReader, f'read_{format_type}', return_value=sample_risk_data):
                    result = risk_aggregator.aggregate_risks(
                        file_path=f'risks.{format_type}',
                        filter_criteria={'severity': ['high', 'critical']},
                        output_format='summary'
                    )
                    
                    assert result is not None
                    assert 'Risk Count by Type' in result
                    assert isinstance(result, str)

    def test_complex_filter_chain_integration(self, risk_aggregator, sample_risk_data):
        """Test multiple filters applied in sequence"""
        with patch.object(RiskFileReader, 'read_csv', return_value=sample_risk_data):
            # Apply multiple filter stages
            filter_stages = [
                {'risk_type': ['market', 'credit']},  # First filter
                {'severity': ['high', 'critical']},    # Second filter
                {'value': {'min': 50000}}              # Third filter
            ]
            
            result = risk_aggregator.aggregate_risks_with_stages(
                file_path='risks.csv',
                filter_stages=filter_stages,
                output_format='detailed'
            )
            
            # Verify filtering worked correctly
            assert 'Filtered Results' in result
            assert 'Stage 1' in result
            assert 'Stage 2' in result
            assert 'Stage 3' in result
            assert 'Final Count: 3' in result

    def test_error_handling_across_layers(self, risk_aggregator):
        """Test error propagation and handling across all layers"""
        
        # Test 1: File not found error from reader layer
        with patch.object(RiskFileReader, 'read_csv', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(FileNotFoundError) as exc_info:
                risk_aggregator.aggregate_risks(
                    file_path='nonexistent.csv',
                    filter_criteria={},
                    output_format='table'
                )
            assert "File not found" in str(exc_info.value)
        
        # Test 2: Invalid filter criteria in filter layer
        invalid_data = pd.DataFrame({'invalid': [1, 2, 3]})
        with patch.object(RiskFileReader, 'read_csv', return_value=invalid_data):
            with pytest.raises(ValueError) as exc_info:
                risk_aggregator.aggregate_risks(
                    file_path='risks.csv',
                    filter_criteria={'risk_type': ['market']},
                    output_format='table'
                )
            assert "Invalid filter column" in str(exc_info.value)
        
        # Test 3: Formatting error in formatter layer
        with patch.object(RiskTableFormatter, 'format_table', side_effect=RuntimeError("Formatting failed")):
            with patch.object(RiskFileReader, 'read_csv', return_value=pd.DataFrame()):
                with pytest.raises(RuntimeError) as exc_info:
                    risk_aggregator.aggregate_risks(
                        file_path='risks.csv',
                        filter_criteria={},
                        output_format='table'
                    )
                assert "Formatting failed" in str(exc_info.value)

    def test_large_dataset_performance_integration(self, risk_aggregator):
        """Test performance with large datasets across all layers"""
        # Generate large dataset
        large_data = pd.DataFrame({
            'risk_id': [f'R{i:06d}' for i in range(100000)],
            'risk_type': ['market', 'credit', 'operational', 'liquidity'] * 25000,
            'severity': ['low', 'medium', 'high', 'critical'] * 25000,
            'value': [i * 100 for i in range(100000)],
            'date': [f'2024-01-{(i % 30) + 1:02d}' for i in range(100000)],
            'department': ['dept1', 'dept2', 'dept3', 'dept4', 'dept5'] * 20000
        })
        
        with patch.object(RiskFileReader, 'read_csv', return_value=large_data):
            import time
            start_time = time.time()
            
            result = risk_aggregator.aggregate_risks(
                file_path='large_risks.csv',
                filter_criteria={
                    'risk_type': ['market', 'credit'],
                    'severity': ['high', 'critical']
                },
                output_format='summary'
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Verify results
            assert result is not None
            assert 'Total Risks: 50,000' in result
            assert processing_time < 5.0  # Should complete within 5 seconds

    def test_output_format_variations_integration(self, risk_aggregator, sample_risk_data):
        """Test different output formats with same input data"""
        with patch.object(RiskFileReader, 'read_csv', return_value=sample_risk_data):
            output_formats = ['table', 'summary', 'json', 'csv', 'html']
            filter_criteria = {'severity': ['high', 'critical']}
            
            results = {}
            for format_type in output_formats:
                try:
                    result = risk_aggregator.aggregate_risks(
                        file_path='risks.csv',
                        filter_criteria=filter_criteria,
                        output_format=format_type
                    )
                    results[format_type] = result
                except NotImplementedError:
                    # Some formats might not be implemented
                    results[format_type] = None
            
            # Verify different formats
            assert results['table'] is not None
            assert isinstance(results['table'], str)
            assert '│' in results['table']  # Table borders
            
            if results['json']:
                assert isinstance(json.loads(results['json']), dict)
            
            if results['html']:
                assert '<table>' in results['html']
                assert '</table>' in results['html']

    def test_concurrent_aggregation_integration(self, risk_aggregator, sample_risk_data):
        """Test concurrent processing of multiple risk files"""
        import concurrent.futures
        
        # Mock multiple files
        files = {
            'risks_q1.csv': sample_risk_data.copy(),
            'risks_q2.csv': sample_risk_data.copy(),
            'risks_q3.csv': sample_risk_data.copy(),
            'risks_q4.csv': sample_risk_data.copy()
        }
        
        def process_file(file_path):
            with patch.object(RiskFileReader, 'read_csv', return_value=files[file_path]):
                return risk_aggregator.aggregate_risks(
                    file_path=file_path,
                    filter_criteria={'severity': ['high', 'critical']},
                    output_format='summary'
                )
        
        # Process files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_file, fp): fp for fp in files.keys()}
            results = {}
            
            for future in concurrent.futures.as_completed(futures):
                file_path = futures[future]
                try:
                    results[file_path] = future.result()
                except Exception as exc:
                    results[file_path] = f'Error: {exc}'
        
        # Verify all files were processed
        assert len(results) == 4
        for file_path, result in results.items():
            assert result is not None
            assert 'Risk Count' in result

    def test_configuration_based_aggregation(self, risk_aggregator, sample_risk_data):
        """Test aggregation using configuration files"""
        config = {
            "input": {
                "file_path": "risks.csv",
                "file_type": "csv"
            },
            "filters": [
                {
                    "column": "risk_type",
                    "values": ["market", "credit"]
                },
                {
                    "column": "severity",
                    "values": ["high", "critical"]
                }
            ],
            "output": {
                "format": "table",
                "include_summary": True,
                "save_to_file": "output.txt"
            }
        }
        
        with patch.object(RiskFileReader, 'read_csv', return_value=sample_risk_data):
            with patch('builtins.open', mock_open()) as mock_file:
                result = risk_aggregator.aggregate_from_config(config)
                
                # Verify result
                assert result is not None
                assert 'Configuration Applied Successfully' in result
                
                # Verify file was written
                mock_file.assert_called_with('output.txt', 'w')

    def test_transaction_rollback_on_error(self, risk_aggregator, sample_risk_data):
        """Test that partial processing is rolled back on error"""
        # Simulate a scenario where processing fails midway
        with patch.object(RiskFileReader, 'read_csv', return_value=sample_risk_data):
            with patch.object(RiskFilterLogic, 'apply_filters') as mock_filter:
                # Make filter fail after first successful call
                mock_filter.side_effect = [sample_risk_data, ValueError("Filter error")]
                
                # Attempt to process multiple operations
                with pytest.raises(ValueError):
                    risk_aggregator.batch_aggregate([
                        {
                            'file_path': 'risks1.csv',
                            'filter_criteria': {'severity': ['high']},
                            'output_format': 'table'
                        },
                        {
                            'file_path': 'risks2.csv',
                            'filter_criteria': {'severity': ['critical']},
                            'output_format': 'table'
                        }
                    ])
                
                # Verify no partial results were saved
                assert risk_aggregator.get_last_results() is None
                assert risk_aggregator.get_processing_status() == 'rolled_back'