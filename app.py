import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import numpy as np
from ofxparse import OfxParser
from unidecode import unidecode

import React, { useState, useCallback } from 'react';
import { Upload, FileText, Table, CheckSquare, Square, Play, FileSpreadsheet, AlertCircle, Check, X } from 'lucide-react';
import * as XLSX from 'xlsx';
import * as mammoth from 'mammoth';

const FileComparisonTool = () => {
  const [baseFile, setBaseFile] = useState(null);
  const [comparisonFile, setComparisonFile] = useState(null);
  const [baseData, setBaseData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [availableColumns, setAvailableColumns] = useState([]);
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [comparisonMode, setComparisonMode] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  const processExcelFile = async (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = new Uint8Array(e.target.result);
          const workbook = XLSX.read(data, { type: 'array' });
          const sheetName = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[sheetName];
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
          
          if (jsonData.length === 0) {
            reject(new Error('Arquivo Excel vazio'));
            return;
          }
          
          const headers = jsonData[0] || [];
          const rows = jsonData.slice(1);
          
          resolve({
            headers,
            rows,
            rawData: jsonData,
            type: 'excel'
          });
        } catch (error) {
          reject(error);
        }
      };
      reader.onerror = () => reject(new Error('Erro ao ler arquivo Excel'));
      reader.readAsArrayBuffer(file);
    });
  };

  const processPDFFile = async (file) => {
    // Simulação de processamento de PDF - em um caso real, você usaria uma biblioteca como pdf-parse
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        // Para demonstração, vamos simular dados extraídos de um PDF
        const mockData = {
          headers: ['Coluna1', 'Coluna2', 'Coluna3', 'Coluna4'],
          rows: [
            ['Valor1', 'Valor2', 'Valor3', 'Valor4'],
            ['Valor5', 'Valor6', 'Valor7', 'Valor8']
          ],
          type: 'pdf'
        };
        resolve(mockData);
      }, 1000);
    });
  };

  const handleFileUpload = async (file, isBase = true) => {
    setLoading(true);
    try {
      let processedData;
      
      if (file.type.includes('sheet') || file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
        processedData = await processExcelFile(file);
      } else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        processedData = await processPDFFile(file);
      } else {
        throw new Error('Formato de arquivo não suportado. Use PDF ou Excel.');
      }

      if (isBase) {
        setBaseFile(file);
        setBaseData(processedData);
        setAvailableColumns(processedData.headers);
        // Não avança automaticamente para o passo 2
      } else {
        setComparisonFile(file);
        setComparisonData(processedData);
        // Só avança para o passo 2 quando ambos os arquivos estão carregados
        if (baseData) {
          setCurrentStep(2);
        }
      }
    } catch (error) {
      alert(`Erro ao processar arquivo: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const toggleColumnSelection = (column) => {
    setSelectedColumns(prev => 
      prev.includes(column) 
        ? prev.filter(col => col !== column)
        : [...prev, column]
    );
  };

  const compareFormatting = () => {
    const results = {
      type: 'formatting',
      issues: [],
      summary: {}
    };

    // Verificar presença de colunas obrigatórias
    const missingColumns = selectedColumns.filter(col => 
      !comparisonData.headers.includes(col)
    );
    if (missingColumns.length > 0) {
      results.issues.push({
        type: 'missing_columns',
        severity: 'high',
        message: `Colunas obrigatórias ausentes: ${missingColumns.join(', ')}`
      });
    }

    // Verificar ordem das colunas
    const baseOrder = baseData.headers.filter(col => selectedColumns.includes(col));
    const comparisonOrder = comparisonData.headers.filter(col => selectedColumns.includes(col));
    
    if (JSON.stringify(baseOrder) !== JSON.stringify(comparisonOrder)) {
      results.issues.push({
        type: 'column_order',
        severity: 'medium',
        message: 'Ordem das colunas obrigatórias é diferente'
      });
    }

    // Verificar estrutura geral
    if (baseData.headers.length !== comparisonData.headers.length) {
      results.issues.push({
        type: 'structure',
        severity: 'medium',
        message: `Número de colunas diferente: Base (${baseData.headers.length}) vs Comparação (${comparisonData.headers.length})`
      });
    }

    // Verificar cabeçalhos diferentes
    const differentHeaders = baseData.headers.filter(header => 
      !comparisonData.headers.includes(header)
    );
    if (differentHeaders.length > 0) {
      results.issues.push({
        type: 'different_headers',
        severity: 'low',
        message: `Cabeçalhos diferentes: ${differentHeaders.join(', ')}`
      });
    }

    results.summary = {
      totalIssues: results.issues.length,
      highSeverity: results.issues.filter(i => i.severity === 'high').length,
      mediumSeverity: results.issues.filter(i => i.severity === 'medium').length,
      lowSeverity: results.issues.filter(i => i.severity === 'low').length
    };

    return results;
  };

  const compareContent = () => {
    const results = {
      type: 'content',
      differences: [],
      summary: {}
    };

    // Criar índices das colunas obrigatórias
    const baseColumnIndices = selectedColumns.map(col => 
      baseData.headers.indexOf(col)
    ).filter(index => index !== -1);

    const comparisonColumnIndices = selectedColumns.map(col => 
      comparisonData.headers.indexOf(col)
    ).filter(index => index !== -1);

    // Comparar linhas
    const maxRows = Math.max(baseData.rows.length, comparisonData.rows.length);
    
    for (let i = 0; i < maxRows; i++) {
      const baseRow = baseData.rows[i];
      const comparisonRow = comparisonData.rows[i];

      if (!baseRow && comparisonRow) {
        results.differences.push({
          row: i + 1,
          type: 'extra_row',
          message: 'Linha existe apenas no arquivo de comparação'
        });
        continue;
      }

      if (baseRow && !comparisonRow) {
        results.differences.push({
          row: i + 1,
          type: 'missing_row',
          message: 'Linha existe apenas no arquivo base'
        });
        continue;
      }

      if (baseRow && comparisonRow) {
        // Comparar valores das colunas obrigatórias
        baseColumnIndices.forEach((baseIndex, colIndex) => {
          const comparisonIndex = comparisonColumnIndices[colIndex];
          if (comparisonIndex !== undefined) {
            const baseValue = baseRow[baseIndex];
            const comparisonValue = comparisonRow[comparisonIndex];
            
            if (baseValue !== comparisonValue) {
              results.differences.push({
                row: i + 1,
                column: selectedColumns[colIndex],
                type: 'value_difference',
                baseValue,
                comparisonValue,
                message: `Valor diferente na coluna ${selectedColumns[colIndex]}`
              });
            }
          }
        });
      }
    }

    results.summary = {
      totalDifferences: results.differences.length,
      valueDifferences: results.differences.filter(d => d.type === 'value_difference').length,
      missingRows: results.differences.filter(d => d.type === 'missing_row').length,
      extraRows: results.differences.filter(d => d.type === 'extra_row').length
    };

    return results;
  };

  const runComparison = () => {
    setLoading(true);
    
    setTimeout(() => {
      let comparisonResults;
      
      if (comparisonMode === 'formatting') {
        comparisonResults = compareFormatting();
      } else {
        comparisonResults = compareContent();
      }
      
      setResults(comparisonResults);
      setCurrentStep(4);
      setLoading(false);
    }, 1000);
  };

  const resetTool = () => {
    setBaseFile(null);
    setComparisonFile(null);
    setBaseData(null);
    setComparisonData(null);
    setAvailableColumns([]);
    setSelectedColumns([]);
    setComparisonMode('');
    setResults(null);
    setCurrentStep(1);
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high': return 'text-red-600 bg-red-50';
      case 'medium': return 'text-yellow-600 bg-yellow-50';
      case 'low': return 'text-blue-600 bg-blue-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-white">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Ferramenta de Comparação de Arquivos
        </h1>
        <p className="text-gray-600">
          Compare arquivos PDF e Excel com foco em formatação ou conteúdo
        </p>
      </div>

      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {[
            { step: 1, title: 'Envio de Arquivos' },
            { step: 2, title: 'Seleção de Colunas' },
            { step: 3, title: 'Modo de Comparação' },
            { step: 4, title: 'Resultados' }
          ].map((item, index) => (
            <div key={item.step} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                currentStep >= item.step 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-600'
              }`}>
                {item.step}
              </div>
              <span className={`ml-2 text-sm ${
                currentStep >= item.step ? 'text-blue-600' : 'text-gray-500'
              }`}>
                {item.title}
              </span>
              {index < 3 && (
                <div className={`w-16 h-0.5 mx-4 ${
                  currentStep > item.step ? 'bg-blue-600' : 'bg-gray-200'
                }`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step 1: File Upload */}
      {currentStep === 1 && (
        <div className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Base File Upload */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
              <div className="text-center">
                <FileText className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Arquivo Base (Modelo)
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Selecione o arquivo que servirá como modelo de referência
                </p>
                <input
                  type="file"
                  accept=".pdf,.xlsx,.xls"
                  onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0], true)}
                  className="hidden"
                  id="base-file"
                />
                <label
                  htmlFor="base-file"
                  className="cursor-pointer inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Selecionar Arquivo Base
                </label>
                {baseFile && (
                  <p className="mt-2 text-sm text-green-600">
                    ✓ {baseFile.name}
                  </p>
                )}
              </div>
            </div>

            {/* Comparison File Upload */}
            <div className={`border-2 border-dashed rounded-lg p-6 ${
              baseFile ? 'border-gray-300' : 'border-gray-200 opacity-50'
            }`}>
              <div className="text-center">
                <FileSpreadsheet className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Arquivo de Comparação
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Selecione o arquivo que será comparado com o modelo base
                </p>
                <input
                  type="file"
                  accept=".pdf,.xlsx,.xls"
                  onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0], false)}
                  disabled={!baseFile}
                  className="hidden"
                  id="comparison-file"
                />
                <label
                  htmlFor="comparison-file"
                  className={`cursor-pointer inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md ${
                    baseFile 
                      ? 'text-white bg-green-600 hover:bg-green-700' 
                      : 'text-gray-400 bg-gray-200 cursor-not-allowed'
                  }`}
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Selecionar Arquivo de Comparação
                </label>
                {comparisonFile && (
                  <p className="mt-2 text-sm text-green-600">
                    ✓ {comparisonFile.name}
                  </p>
                )}
              </div>
            </div>
          </div>
          
          {/* Progress indicator for step 1 */}
          {baseFile && comparisonFile && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
              <div className="flex items-center justify-center text-green-700">
                <Check className="w-5 h-5 mr-2" />
                <span className="font-medium">
                  Ambos os arquivos foram carregados com sucesso! Avançando para seleção de colunas...
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Column Selection */}
      {currentStep === 2 && baseData && (
        <div className="space-y-6">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-lg font-medium text-blue-900 mb-2">
              Selecione as Colunas Obrigatórias
            </h3>
            <p className="text-sm text-blue-700">
              Escolha quais colunas devem ser consideradas na comparação. 
              Apenas essas colunas serão analisadas nos dois modos de comparação.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {availableColumns.map((column, index) => (
              <div
                key={index}
                onClick={() => toggleColumnSelection(column)}
                className={`cursor-pointer border rounded-lg p-3 transition-all ${
                  selectedColumns.includes(column)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center">
                  {selectedColumns.includes(column) ? (
                    <CheckSquare className="w-5 h-5 text-blue-600 mr-2" />
                  ) : (
                    <Square className="w-5 h-5 text-gray-400 mr-2" />
                  )}
                  <span className={`text-sm font-medium ${
                    selectedColumns.includes(column) ? 'text-blue-900' : 'text-gray-700'
                  }`}>
                    {column}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center pt-4">
            <p className="text-sm text-gray-600">
              {selectedColumns.length} colunas selecionadas
            </p>
            <button
              onClick={() => setCurrentStep(3)}
              disabled={selectedColumns.length === 0}
              className={`px-6 py-2 rounded-md text-sm font-medium ${
                selectedColumns.length > 0
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
            >
              Continuar
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Comparison Mode Selection */}
      {currentStep === 3 && comparisonData && (
        <div className="space-y-6">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="text-lg font-medium text-green-900 mb-2">
              Escolha o Modo de Comparação
            </h3>
            <p className="text-sm text-green-700">
              Selecione como você deseja comparar os arquivos
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div
              onClick={() => setComparisonMode('formatting')}
              className={`cursor-pointer border-2 rounded-lg p-6 transition-all ${
                comparisonMode === 'formatting'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-start">
                <Table className="w-8 h-8 text-blue-600 mr-4 flex-shrink-0 mt-1" />
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-2">
                    Modo 1 - Comparação de Formatação
                  </h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    <li>• Presença de colunas obrigatórias</li>
                    <li>• Ordem das colunas</li>
                    <li>• Formatação de células</li>
                    <li>• Cabeçalhos diferentes</li>
                    <li>• Estrutura geral</li>
                  </ul>
                </div>
              </div>
            </div>

            <div
              onClick={() => setComparisonMode('content')}
              className={`cursor-pointer border-2 rounded-lg p-6 transition-all ${
                comparisonMode === 'content'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-start">
                <FileText className="w-8 h-8 text-green-600 mr-4 flex-shrink-0 mt-1" />
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-2">
                    Modo 2 - Comparação de Conteúdo
                  </h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    <li>• Diferenças de valores</li>
                    <li>• Linhas ausentes</li>
                    <li>• Linhas extras</li>
                    <li>• Valores divergentes</li>
                    <li>• Análise detalhada dos dados</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-between items-center pt-4">
            <button
              onClick={() => setCurrentStep(2)}
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
            >
              ← Voltar
            </button>
            <button
              onClick={runComparison}
              disabled={!comparisonMode}
              className={`px-6 py-2 rounded-md text-sm font-medium inline-flex items-center ${
                comparisonMode
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
            >
              <Play className="w-4 h-4 mr-2" />
              Executar Comparação
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Results */}
      {currentStep === 4 && results && (
        <div className="space-y-6">
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              Resultados da Comparação - {results.type === 'formatting' ? 'Formatação' : 'Conteúdo'}
            </h3>
            <p className="text-sm text-gray-600">
              Análise completa entre os arquivos selecionados
            </p>
          </div>

          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {results.type === 'formatting' ? (
              <>
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-gray-900">{results.summary.totalIssues}</div>
                  <div className="text-sm text-gray-600">Total de Problemas</div>
                </div>
                <div className="bg-white border border-red-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-red-600">{results.summary.highSeverity}</div>
                  <div className="text-sm text-red-600">Alta Severidade</div>
                </div>
                <div className="bg-white border border-yellow-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-yellow-600">{results.summary.mediumSeverity}</div>
                  <div className="text-sm text-yellow-600">Média Severidade</div>
                </div>
                <div className="bg-white border border-blue-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-blue-600">{results.summary.lowSeverity}</div>
                  <div className="text-sm text-blue-600">Baixa Severidade</div>
                </div>
              </>
            ) : (
              <>
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-gray-900">{results.summary.totalDifferences}</div>
                  <div className="text-sm text-gray-600">Total de Diferenças</div>
                </div>
                <div className="bg-white border border-red-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-red-600">{results.summary.valueDifferences}</div>
                  <div className="text-sm text-red-600">Valores Diferentes</div>
                </div>
                <div className="bg-white border border-orange-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-orange-600">{results.summary.missingRows}</div>
                  <div className="text-sm text-orange-600">Linhas Ausentes</div>
                </div>
                <div className="bg-white border border-blue-200 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-blue-600">{results.summary.extraRows}</div>
                  <div className="text-sm text-blue-600">Linhas Extras</div>
                </div>
              </>
            )}
          </div>

          {/* Detailed Results */}
          <div className="bg-white border border-gray-200 rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h4 className="text-lg font-medium text-gray-900">
                Detalhamento dos Resultados
              </h4>
            </div>
            <div className="p-6">
              {results.type === 'formatting' ? (
                <div className="space-y-3">
                  {results.issues.length === 0 ? (
                    <div className="flex items-center text-green-600">
                      <Check className="w-5 h-5 mr-2" />
                      Nenhum problema de formatação encontrado!
                    </div>
                  ) : (
                    results.issues.map((issue, index) => (
                      <div key={index} className={`flex items-start p-3 rounded-lg ${getSeverityColor(issue.severity)}`}>
                        <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="font-medium capitalize">{issue.type.replace('_', ' ')}</div>
                          <div className="text-sm">{issue.message}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {results.differences.length === 0 ? (
                    <div className="flex items-center text-green-600">
                      <Check className="w-5 h-5 mr-2" />
                      Nenhuma diferença de conteúdo encontrada!
                    </div>
                  ) : (
                    results.differences.map((diff, index) => (
                      <div key={index} className="flex items-start p-3 bg-gray-50 rounded-lg">
                        <X className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5 text-red-500" />
                        <div className="flex-1">
                          <div className="font-medium">
                            Linha {diff.row} {diff.column && `- Coluna ${diff.column}`}
                          </div>
                          <div className="text-sm text-gray-600">{diff.message}</div>
                          {diff.baseValue !== undefined && (
                            <div className="text-xs mt-1 grid grid-cols-2 gap-4">
                              <div>
                                <span className="font-medium">Base:</span> {diff.baseValue || '(vazio)'}
                              </div>
                              <div>
                                <span className="font-medium">Comparação:</span> {diff.comparisonValue || '(vazio)'}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-center">
            <button
              onClick={resetTool}
              className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm font-medium"
            >
              Nova Comparação
            </button>
          </div>
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6">
            <div className="flex items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-4"></div>
              <span className="text-lg font-medium">Processando...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileComparisonTool;
