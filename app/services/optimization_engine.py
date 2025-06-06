"""
最適化エンジン
遺伝的アルゴリズム、グリッドサーチ等による戦略パラメータ最適化
"""

import random
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import logging
import json
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.core.database import get_db_connection
from app.services.backtest_engine import BacktestEngine

logger = logging.getLogger(__name__)

class OptimizationEngine:
    def __init__(self):
        self.backtest_engine = BacktestEngine()
        
    async def run_optimization(
        self,
        optimization_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        optimization_type: str,
        objective_function: str,
        max_iterations: int,
        population_size: int,
        parameters: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        最適化を実行
        """
        try:
            if optimization_type == "genetic_algorithm":
                return await self._genetic_algorithm_optimization(
                    optimization_id, symbol, start_date, end_date,
                    objective_function, max_iterations, population_size, parameters
                )
            elif optimization_type == "grid_search":
                return await self._grid_search_optimization(
                    optimization_id, symbol, start_date, end_date,
                    objective_function, parameters
                )
            elif optimization_type == "random_search":
                return await self._random_search_optimization(
                    optimization_id, symbol, start_date, end_date,
                    objective_function, max_iterations, parameters
                )
            elif optimization_type == "bayesian_optimization":
                return await self._bayesian_optimization(
                    optimization_id, symbol, start_date, end_date,
                    objective_function, max_iterations, parameters
                )
            else:
                raise ValueError(f"未対応の最適化タイプ: {optimization_type}")
                
        except Exception as e:
            logger.error(f"最適化実行エラー: {str(e)}")
            raise
    
    async def _genetic_algorithm_optimization(
        self,
        optimization_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        objective_function: str,
        max_generations: int,
        population_size: int,
        parameters: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        遺伝的アルゴリズムによる最適化
        """
        try:
            logger.info(f"遺伝的アルゴリズム開始: 世代数={max_generations}, 個体数={population_size}")
            
            # 初期集団を生成
            population = self._generate_initial_population(parameters, population_size)
            best_individual = None
            best_score = float('-inf') if self._is_maximization_objective(objective_function) else float('inf')
            generation_scores = []
            
            for generation in range(max_generations):
                # 各個体を評価
                scored_population = []
                
                for individual in population:
                    score = await self._evaluate_individual(
                        individual, symbol, start_date, end_date, objective_function
                    )
                    scored_population.append((individual, score))
                    
                    # 最良個体を更新
                    if self._is_better_score(score, best_score, objective_function):
                        best_score = score
                        best_individual = individual.copy()
                
                # 世代の統計を記録
                scores = [score for _, score in scored_population]
                avg_score = np.mean(scores)
                generation_scores.append({
                    'generation': generation,
                    'best_score': best_score,
                    'avg_score': avg_score,
                    'min_score': min(scores),
                    'max_score': max(scores)
                })
                
                # 履歴を保存
                await self._save_optimization_history(
                    optimization_id, generation, best_individual, best_score, {
                        'avg_score': avg_score,
                        'population_size': len(population)
                    }
                )
                
                logger.info(f"世代 {generation}: 最良スコア={best_score:.4f}, 平均スコア={avg_score:.4f}")
                
                # 早期終了条件チェック
                if await self._should_stop_optimization(optimization_id):
                    logger.info("最適化が外部から停止されました")
                    break
                
                # 次世代を生成
                if generation < max_generations - 1:
                    population = self._generate_next_generation(
                        scored_population, parameters, population_size
                    )
            
            return {
                'best_parameters': best_individual,
                'best_score': best_score,
                'total_iterations': generation + 1,
                'generation_scores': generation_scores
            }
            
        except Exception as e:
            logger.error(f"遺伝的アルゴリズム最適化エラー: {str(e)}")
            raise
    
    async def _grid_search_optimization(
        self,
        optimization_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        objective_function: str,
        parameters: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        グリッドサーチによる最適化
        """
        try:
            logger.info("グリッドサーチ開始")
            
            # パラメータグリッドを生成
            parameter_grid = self._generate_parameter_grid(parameters)
            total_combinations = len(parameter_grid)
            
            logger.info(f"総組み合わせ数: {total_combinations}")
            
            best_parameters = None
            best_score = float('-inf') if self._is_maximization_objective(objective_function) else float('inf')
            
            for i, param_combination in enumerate(parameter_grid):
                # 個体を評価
                score = await self._evaluate_individual(
                    param_combination, symbol, start_date, end_date, objective_function
                )
                
                # 最良パラメータを更新
                if self._is_better_score(score, best_score, objective_function):
                    best_score = score
                    best_parameters = param_combination.copy()
                
                # 履歴を保存
                await self._save_optimization_history(
                    optimization_id, i, param_combination, score, {
                        'progress': (i + 1) / total_combinations
                    }
                )
                
                if (i + 1) % 10 == 0:
                    logger.info(f"進捗: {i + 1}/{total_combinations}, 現在の最良スコア: {best_score:.4f}")
                
                # 早期終了条件チェック
                if await self._should_stop_optimization(optimization_id):
                    logger.info("最適化が外部から停止されました")
                    break
            
            return {
                'best_parameters': best_parameters,
                'best_score': best_score,
                'total_iterations': min(i + 1, total_combinations)
            }
            
        except Exception as e:
            logger.error(f"グリッドサーチ最適化エラー: {str(e)}")
            raise
    
    async def _random_search_optimization(
        self,
        optimization_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        objective_function: str,
        max_iterations: int,
        parameters: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ランダムサーチによる最適化
        """
        try:
            logger.info(f"ランダムサーチ開始: 反復数={max_iterations}")
            
            best_parameters = None
            best_score = float('-inf') if self._is_maximization_objective(objective_function) else float('inf')
            
            for iteration in range(max_iterations):
                # ランダムパラメータを生成
                random_params = self._generate_random_parameters(parameters)
                
                # 個体を評価
                score = await self._evaluate_individual(
                    random_params, symbol, start_date, end_date, objective_function
                )
                
                # 最良パラメータを更新
                if self._is_better_score(score, best_score, objective_function):
                    best_score = score
                    best_parameters = random_params.copy()
                
                # 履歴を保存
                await self._save_optimization_history(
                    optimization_id, iteration, random_params, score, {}
                )
                
                if (iteration + 1) % 20 == 0:
                    logger.info(f"反復: {iteration + 1}/{max_iterations}, 最良スコア: {best_score:.4f}")
                
                # 早期終了条件チェック
                if await self._should_stop_optimization(optimization_id):
                    logger.info("最適化が外部から停止されました")
                    break
            
            return {
                'best_parameters': best_parameters,
                'best_score': best_score,
                'total_iterations': iteration + 1
            }
            
        except Exception as e:
            logger.error(f"ランダムサーチ最適化エラー: {str(e)}")
            raise
    
    async def _bayesian_optimization(
        self,
        optimization_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        objective_function: str,
        max_iterations: int,
        parameters: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ベイズ最適化（簡易版）
        """
        try:
            logger.info(f"ベイズ最適化開始: 反復数={max_iterations}")
            
            # 初期サンプリング
            initial_samples = 10
            samples = []
            scores = []
            
            for i in range(min(initial_samples, max_iterations)):
                params = self._generate_random_parameters(parameters)
                score = await self._evaluate_individual(
                    params, symbol, start_date, end_date, objective_function
                )
                
                samples.append(params)
                scores.append(score)
                
                await self._save_optimization_history(
                    optimization_id, i, params, score, {'phase': 'initial_sampling'}
                )
            
            best_idx = np.argmax(scores) if self._is_maximization_objective(objective_function) else np.argmin(scores)
            best_parameters = samples[best_idx]
            best_score = scores[best_idx]
            
            # 残りの反復でベイズ最適化を実行
            for iteration in range(initial_samples, max_iterations):
                # 次の探索点を決定（簡易版：最良点周辺をランダム探索）
                next_params = self._generate_next_bayesian_point(best_parameters, parameters)
                
                score = await self._evaluate_individual(
                    next_params, symbol, start_date, end_date, objective_function
                )
                
                samples.append(next_params)
                scores.append(score)
                
                # 最良点を更新
                if self._is_better_score(score, best_score, objective_function):
                    best_score = score
                    best_parameters = next_params.copy()
                
                await self._save_optimization_history(
                    optimization_id, iteration, next_params, score, {'phase': 'bayesian_search'}
                )
                
                if (iteration + 1) % 10 == 0:
                    logger.info(f"反復: {iteration + 1}/{max_iterations}, 最良スコア: {best_score:.4f}")
                
                if await self._should_stop_optimization(optimization_id):
                    break
            
            return {
                'best_parameters': best_parameters,
                'best_score': best_score,
                'total_iterations': len(samples)
            }
            
        except Exception as e:
            logger.error(f"ベイズ最適化エラー: {str(e)}")
            raise
    
    def _generate_initial_population(self, parameters: Dict[str, Dict[str, Any]], size: int) -> List[Dict[str, Any]]:
        """
        初期集団を生成
        """
        population = []
        for _ in range(size):
            individual = self._generate_random_parameters(parameters)
            population.append(individual)
        return population
    
    def _generate_random_parameters(self, parameters: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        ランダムパラメータを生成
        """
        params = {}
        for param_name, param_config in parameters.items():
            param_type = param_config.get('type', 'float')
            min_val = param_config['min_value']
            max_val = param_config['max_value']
            
            if param_type == 'int':
                params[param_name] = random.randint(min_val, max_val)
            elif param_type == 'float':
                params[param_name] = random.uniform(min_val, max_val)
            elif param_type == 'choice':
                choices = param_config.get('choices', [min_val, max_val])
                params[param_name] = random.choice(choices)
        
        return params
    
    def _generate_parameter_grid(self, parameters: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        グリッドサーチ用のパラメータグリッドを生成
        """
        param_lists = {}
        
        for param_name, param_config in parameters.items():
            param_type = param_config.get('type', 'float')
            min_val = param_config['min_value']
            max_val = param_config['max_value']
            step = param_config.get('step', 1 if param_type == 'int' else 0.1)
            
            if param_type == 'int':
                param_lists[param_name] = list(range(min_val, max_val + 1, int(step)))
            elif param_type == 'float':
                param_lists[param_name] = []
                current = min_val
                while current <= max_val:
                    param_lists[param_name].append(round(current, 2))
                    current += step
            elif param_type == 'choice':
                param_lists[param_name] = param_config.get('choices', [min_val, max_val])
        
        # 全組み合わせを生成
        grid = []
        self._generate_combinations(param_lists, {}, list(param_lists.keys()), 0, grid)
        
        return grid
    
    def _generate_combinations(self, param_lists: Dict, current: Dict, keys: List, index: int, result: List):
        """
        再帰的に全組み合わせを生成
        """
        if index == len(keys):
            result.append(current.copy())
            return
        
        key = keys[index]
        for value in param_lists[key]:
            current[key] = value
            self._generate_combinations(param_lists, current, keys, index + 1, result)
    
    def _generate_next_generation(
        self, 
        scored_population: List[Tuple[Dict, float]], 
        parameters: Dict[str, Dict[str, Any]], 
        population_size: int
    ) -> List[Dict[str, Any]]:
        """
        次世代を生成（選択、交叉、突然変異）
        """
        # スコアでソート（最適化目的に応じて）
        scored_population.sort(key=lambda x: x[1], reverse=True)  # 降順でソート
        
        # エリート選択（上位20%を保持）
        elite_size = max(1, population_size // 5)
        next_generation = [individual for individual, _ in scored_population[:elite_size]]
        
        # 残りを交叉と突然変異で生成
        while len(next_generation) < population_size:
            # 親を選択（トーナメント選択）
            parent1 = self._tournament_selection(scored_population)
            parent2 = self._tournament_selection(scored_population)
            
            # 交叉
            child = self._crossover(parent1, parent2, parameters)
            
            # 突然変異
            child = self._mutate(child, parameters, mutation_rate=0.1)
            
            next_generation.append(child)
        
        return next_generation[:population_size]
    
    def _tournament_selection(self, scored_population: List[Tuple[Dict, float]], tournament_size: int = 3) -> Dict[str, Any]:
        """
        トーナメント選択
        """
        tournament = random.sample(scored_population, min(tournament_size, len(scored_population)))
        winner = max(tournament, key=lambda x: x[1])  # 最高スコアを選択
        return winner[0]
    
    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any], parameters: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        交叉（一様交叉）
        """
        child = {}
        for param_name in parameters.keys():
            if random.random() < 0.5:
                child[param_name] = parent1[param_name]
            else:
                child[param_name] = parent2[param_name]
        return child
    
    def _mutate(self, individual: Dict[str, Any], parameters: Dict[str, Dict[str, Any]], mutation_rate: float) -> Dict[str, Any]:
        """
        突然変異
        """
        mutated = individual.copy()
        
        for param_name, param_config in parameters.items():
            if random.random() < mutation_rate:
                param_type = param_config.get('type', 'float')
                min_val = param_config['min_value']
                max_val = param_config['max_value']
                
                if param_type == 'int':
                    mutated[param_name] = random.randint(min_val, max_val)
                elif param_type == 'float':
                    # ガウシアン突然変異
                    current_val = mutated[param_name]
                    mutation_strength = (max_val - min_val) * 0.1
                    new_val = current_val + random.gauss(0, mutation_strength)
                    mutated[param_name] = max(min_val, min(max_val, new_val))
                elif param_type == 'choice':
                    choices = param_config.get('choices', [min_val, max_val])
                    mutated[param_name] = random.choice(choices)
        
        return mutated
    
    def _generate_next_bayesian_point(self, best_params: Dict[str, Any], parameters: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        ベイズ最適化の次の探索点を生成（簡易版）
        """
        next_params = best_params.copy()
        
        # 最良点の周辺をランダム探索
        for param_name, param_config in parameters.items():
            param_type = param_config.get('type', 'float')
            min_val = param_config['min_value']
            max_val = param_config['max_value']
            current_val = best_params[param_name]
            
            if param_type == 'int':
                search_range = max(1, (max_val - min_val) // 10)
                new_val = current_val + random.randint(-search_range, search_range)
                next_params[param_name] = max(min_val, min(max_val, new_val))
            elif param_type == 'float':
                search_range = (max_val - min_val) * 0.2
                new_val = current_val + random.uniform(-search_range, search_range)
                next_params[param_name] = max(min_val, min(max_val, new_val))
        
        return next_params
    
    async def _evaluate_individual(
        self, 
        parameters: Dict[str, Any], 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        objective_function: str
    ) -> float:
        """
        個体（パラメータセット）を評価
        """
        try:
            # バックテストを実行
            result = await self.backtest_engine.run_backtest(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                parameters=parameters,
                initial_balance=100000.0,
                risk_per_trade=0.02,
                max_positions=3
            )
            
            # 目的関数に応じてスコアを計算
            if objective_function == "sharpe_ratio":
                return result.get('sharpe_ratio', 0) or 0
            elif objective_function == "total_profit":
                return result.get('total_profit', 0)
            elif objective_function == "win_rate":
                return result.get('win_rate', 0)
            elif objective_function == "profit_factor":
                return result.get('profit_factor', 0) or 0
            elif objective_function == "max_drawdown":
                return -result.get('max_drawdown', 100)  # 最小化のため負の値
            else:
                return result.get('total_profit', 0)
                
        except Exception as e:
            logger.error(f"個体評価エラー: {str(e)}")
            return float('-inf')  # エラー時は最悪スコア
    
    def _is_maximization_objective(self, objective_function: str) -> bool:
        """
        最大化目的かどうかを判定
        """
        maximization_objectives = ["sharpe_ratio", "total_profit", "win_rate", "profit_factor"]
        return objective_function in maximization_objectives
    
    def _is_better_score(self, new_score: float, current_best: float, objective_function: str) -> bool:
        """
        新しいスコアが現在の最良スコアより良いかを判定
        """
        if self._is_maximization_objective(objective_function):
            return new_score > current_best
        else:
            return new_score < current_best
    
    async def _save_optimization_history(
        self, 
        optimization_id: int, 
        iteration: int, 
        parameters: Dict[str, Any], 
        score: float, 
        metrics: Dict[str, Any]
    ):
        """
        最適化履歴を保存
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO optimization_history 
                (optimization_id, iteration, parameters, score, metrics)
                VALUES (?, ?, ?, ?, ?)
            """, (
                optimization_id,
                iteration,
                json.dumps(parameters),
                score,
                json.dumps(metrics)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"最適化履歴保存エラー: {str(e)}")
    
    async def _should_stop_optimization(self, optimization_id: int) -> bool:
        """
        最適化を停止すべきかチェック
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT status FROM optimization_jobs WHERE id = ?", (optimization_id,))
            row = cursor.fetchone()
            conn.close()
            
            return row and row[0] == 'stopped'
            
        except Exception as e:
            logger.error(f"停止チェックエラー: {str(e)}")
            return False